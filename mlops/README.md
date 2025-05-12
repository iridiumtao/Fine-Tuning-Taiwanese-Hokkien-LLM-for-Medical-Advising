# Fine-Tuning Taiwanese Hokkien LLM for Medical Advising

This repository contains Jupyter notebooks and resources for fine-tuning a Taiwanese Hokkien language model (LLM) specifically for medical advising purposes. The project is structured to demonstrate the MLOps workflow, from data preparation to model deployment.

## Project Structure

The `mlops` folder contains the following Jupyter notebooks:

1. **Environment Setup (`1_setup_env.ipynb`)**  
    - Prepares the infrastructure-as-code (IaC) environment on Chameleon Cloud using a custom bare metal setup.
    - **Clone MLOps Repository (iac folder only)**  
      Uses `git sparse-checkout` to download only the `iac/` folder, saving space.
      ```bash
      git clone --branch mlops --single-branch --filter=blob:none --no-checkout https://github.com/LawrenceLu0904/Fine-Tuning-Taiwanese-Hokkien-LLM-for-Medical-Advising.git
      cd Fine-Tuning-Taiwanese-Hokkien-LLM-for-Medical-Advising
      git sparse-checkout init --cone
      git sparse-checkout set iac
      git checkout
      ```
    - **Install Terraform (v1.10.5)**  
      Installs Terraform locally under `~/.local/bin`.
    - **Install Kubespray Requirements**  
      Installs Python packages required for deploying Kubernetes with Kubespray.

2. **Provision Infrastructure (`2_provision_tf.ipynb`)**  
    - Uses Terraform to provision network interfaces and floating IPs on CHI@UC.
    - Since Terraform cannot provision bare metal nodes directly, the nodes must be reserved via lease first (see **Create a Lease**).

    - **Clarification: No `openstack_compute_instance_v2` Used**  
      In VM-based tutorials (like `kvm@tacc`), instances are created like this:
      ```hcl
      resource "openstack_compute_instance_v2" "my_vm" {
        name        = "${var.instance_hostname}"
        flavor_name = "m1.small"
        image_id    = data.openstack_images_image_v2.ubuntu.id
        key_pair    = "my-keypair"
        network {
          name = "private-network"
        }
      }
      ```
      However, in our setup, we use **bare metal nodes** (e.g., `compute_gigaio`) that are reserved manually via Horizon leases. **Terraform cannot create bare metal nodes**, so we omit this block entirely.

      > Instead, Terraform will only handle:
      > - Network ports (`openstack_networking_port_v2`)
      > - Floating IPs (`openstack_networking_floatingip_v2`)
      > - Security groups and interface attachments

        - **Create Private Network (MLOps Internal Use)**  
      Terraform defines a private network (`192.168.1.0/24`) for internal communication between bare metal nodes (e.g., node1, node2, node3).
      ```hcl
      resource "openstack_networking_network_v2" "private_net" {
        name                  = "private-net-mlops-${var.suffix}"
        port_security_enabled = false
      }

      resource "openstack_networking_subnet_v2" "private_subnet" {
        name       = "private-subnet-mlops-${var.suffix}"
        network_id = openstack_networking_network_v2.private_net.id
        cidr       = "192.168.1.0/24"
        no_gateway = true
      }
      ```

    - **Reference Shared Network and Security Groups**  
      These `data` blocks are used to reference existing shared Chameleon Cloud resources.
      - `sharednet1`: public-facing shared network (used for floating IPs)
      - Security groups: pre-defined access rules for common ports

      > These `data` resources do **not** create anything. They fetch info about already existing networks and security groups in your Chameleon project.

        - **Initialize and Apply Terraform Configuration**  
      After defining the network and security group resources, use the following Terraform commands to provision the infrastructure.

      - Initialize Terraform with provider plugins:
        ```bash
        terraform init -upgrade
        ```

      - Validate the Terraform configuration:
        ```bash
        terraform validate
        ```

      - (Optional) Preview the changes without applying them:
        ```bash
        terraform plan
        ```

      - Apply the Terraform plan to provision resources:
        ```bash
        terraform apply -auto-approve
        ```

      > This will create:
      > - A private internal network (`private-net-mlops-*`)
      > - A subnet (`192.168.1.0/24`)
      > - Any security group associations or port references defined in `.tf` files

    - **Export Terraform Outputs to JSON (for next notebook)**  
      After infrastructure is provisioned, export the resulting variables (like subnet ID, floating IP, etc.) to a JSON file that can be read by the next notebook (`2_5_create_nodes.ipynb`).

      ```bash
      terraform output -json > outputs.json
      ```

      > This file (`outputs.json`) will be parsed in the next step to configure the Ansible inventory and playbooks accordingly.

3. **Create Nodes (`2_5_create_nodes.ipynb`)**  
    - This step provisions the **bare metal nodes** (node1, node2, node3) from your active lease and attaches network ports.
    - It also injects initial configuration into each node using `user_data`.

    - **Set Chameleon Context and Load Leases**
      Selects the active Chameleon project and site (`CHI@UC`) using `python-chi`.
      ```python
      from chi import context
      context.version = "1.0" 
      context.choose_project()
      context.choose_site(default="CHI@UC")
      ```

    - **Load Lease IDs for Each Node**
      Maps lease names (`compute_gigaio_project46_1/2/3`) to reservation IDs for provisioning.

    - **Load Network Ports from Terraform Output**
      Loads port IDs from the previously generated `outputs.json`.

    - **Set Node Metadata via `user_data`**
      Each node is initialized with a shell script passed to `user_data`. This script performs two key tasks:
      
      ```bash
      #!/bin/bash
      echo '127.0.1.1 {node}-mlops' >> /etc/hosts
      su cc -c /usr/local/bin/cc-load-public-keys
      ```

      > Explanation:
      > - `echo '127.0.1.1 {node}-mlops' >> /etc/hosts`  
      >   This ensures that the node has a resolvable hostname inside `/etc/hosts`, important for internal hostname resolution when Ansible or Kubernetes expects the node to know its hostname.
      >
      > - `su cc -c /usr/local/bin/cc-load-public-keys`  
      >   This loads the **Chameleon public SSH key** into the default user (`cc`) so you can SSH into the node after boot. Without this, login would fail unless you manually add keys later.

    - **Result**
      After this notebook:
      - All three nodes (node1, node2, node3) are provisioned with ports, hostname set, and SSH keys installed.
      - Nodes are now reachable (after floating IP is bound to node1).

4. **Configure SSH Access for Ansible (`3_practice_ansible.ipynb`)**  
    - This step configures SSH access so that `node1` (which has a floating IP) can serve as a jump host for `node2` and `node3`.
    - This setup is **essential for bare metal deployments** on CHI@UC because only one node has external network access.

    ---

    ### Why `~/.ssh/config` Is Needed (Not in Original Tutorial)

    In the original `kvm@tacc` VM-based tutorial, all VMs have public IPs and can be accessed directly.  
    But in **bare metal environments**, only `node1` has a floating IP — `node2` and `node3` are only reachable via the **internal private network**.

    To allow tools like **Ansible** to reach those internal nodes automatically, we define a **jump host (proxy) configuration** in `~/.ssh/config`.  
    This enables seamless SSH routing without manually typing jump commands.

    ---

    - Step-by-Step SSH Configuration

        1. Step 1: Copy SSH Private Key to `node1` (from local machine)

            You need to upload your private key to `node1` so that it can later use it to access `node2` and `node3`.(Floating ip 192.5.87.178 
            might be changed)

        2. Step 2: Configure SSH Daemon on `node1`

        3. Step 3: Distribute Public Key to Other Nodes

        4. Step 4: Edit `~/.ssh/config` on Your Local Machine to automate proxying to internal nodes
    > **Result:**  
    > You can now run `ssh node2` and `ssh node3` from your local machine (or Ansible) without manually setting up proxy commands each time.

    - `ansible -i inventory.yml all -m ping`
        This command tells Ansible to:
        - Use the file `inventory.yml` as the host list
        - Run the `ping` module (built-in)
        - Try connecting to all hosts listed under `all`

    - `ansible-playbook -i inventory.yml general/hello_host.yml`
        This command runs a small Ansible playbook (`hello_host.yml`) that you prepared to check hostnames.





## How to Use
1. **Create a Lease (`CHI@UC` Bare Metal Reservation)**  
    - To use bare metal resources on Chameleon, we must reserve them in advance.
    - Use the **OpenStack Horizon GUI** to request `compute_gigaio` nodes.
    - Steps:
      1. Go to [Chameleon Cloud website](https://www.chameleoncloud.org/)
      2. Click “**Experiment**” > “**CHI@UC**”
      3. Log in with your Chameleon account
      4. In the Horizon Dashboard, click on **Reservations** > **Leases**
      5. Click **Create Lease**
      6. Fill in:
         - **Name**: e.g. `compute_gigaio_project46_1`, `compute_gigaio_project46_2`,`compute_gigaio_project46_3`,
         - **Start/End time**: Choose your working time range
         - **Reservation**: Choose `compute_gigaio` (bare metal) as needed
      7. Click **Submit**

2. Run the notebooks in order:
    - Start with `1_setup_env.ipynb`.
    - `2_provision_tf.ipynb`.
    - `2_5_create_nodes.ipynb`.
    - `3_practice_ansible.ipynb`.
    - `4_deploy_k8s.ipynb`
    - `5_configure_argocd.ipynb`
    - `6_lifecycle_part_1.ipynb`
    - `7_lifecycle_part_2.ipynb`
    - `8_delete.ipynb`

## Goals

- Develop a specialized LLM for medical advising in Taiwanese Hokkien.
- Showcase the MLOps lifecycle, including data preparation, model training, evaluation, and deployment.
- Provide a reproducible workflow for similar projects.

## Acknowledgments

This project is part of the NYU MLOps course final assignment. Special thanks to the course instructors and contributors for their guidance.
