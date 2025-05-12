data "openstack_networking_network_v2" "sharednet1" {
  name = "sharednet1"
}

data "openstack_networking_subnet_v2" "sharednet1_subnet" {
  name = "sharednet1-subnet"
}

data "openstack_networking_secgroup_v2" "allow_ssh" {
  name = "allow-ssh"
}

data "openstack_networking_secgroup_v2" "allow_8000" {
  name = "allow-8000"
}

data "openstack_networking_secgroup_v2" "allow_8888" {
  name = "allow-8888"
}

data "openstack_networking_secgroup_v2" "allow_9090" {
  name = "allow-9090"
}

data "openstack_networking_secgroup_v2" "allow_3000" {
  name = "allow-3000"
}