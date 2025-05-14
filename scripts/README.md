### **Link to object storage**

Before starting any train, link to persistant storage.

Set up rclone

``` bash
# run on node-persist
curl https://rclone.org/install.sh | sudo bash
``` 

``` bash
# run on node-persist
# this line makes sure user_allow_other is un-commented in /etc/fuse.conf
sudo sed -i '/^#user_allow_other/s/^#//' /etc/fuse.conf
``` 

``` bash
# run on node
mkdir -p ~/.config/rclone
nano  ~/.config/rclone/rclone.conf
``` 

Fill in your application_credential
```bash
[chi_tacc]
type = swift
user_id = YOUR_USER_ID
application_credential_id = APP_CRED_ID
application_credential_secret = APP_CRED_SECRET
auth = https://chi.tacc.chameleoncloud.org:5000/v3
region = CHI@TACC
```

Mount the object store

``` bash
# run on node
sudo mkdir -p /mnt/object
sudo chown -R cc /mnt/object
sudo chgrp -R cc /mnt/object
``` 

Replace with your container name
``` bash
# run on node
rclone mount chi_tacc:object-persist-project46 /mnt/object --read-only --allow-other --daemon
``` 

Run
``` bash
# run on node
ls /mnt/object
``` 
to confirm there is the data directories. 

Create directory for models
``` bash
# run on node
mkdir models
sudo chmod 1777 /home/cc/Fine-Tuning-Taiwanese-Hokkien-LLM-for-Medical-Advising/models
``` 


Confirm the newest version of model and create symlink
``` bash
# run on node
ln -s /mnt/object/models/v1/stage1 /home/cc/Fine-Tuning-Taiwanese-Hokkien-LLM-for-Medical-Advising/models
ln -s /mnt/object/models/v1/stage2 /home/cc/Fine-Tuning-Taiwanese-Hokkien-LLM-for-Medical-Advising/models
``` 