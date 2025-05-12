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
