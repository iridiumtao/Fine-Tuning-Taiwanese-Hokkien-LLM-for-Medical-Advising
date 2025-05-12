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

resource "openstack_networking_port_v2" "private_net_ports" {
  for_each              = var.nodes
  name                  = "port-${each.key}-mlops-${var.suffix}"
  network_id            = openstack_networking_network_v2.private_net.id
  port_security_enabled = false

  fixed_ip {
    subnet_id  = openstack_networking_subnet_v2.private_subnet.id
    ip_address = each.value
  }
}

resource "openstack_networking_port_v2" "sharednet1_ports" {
  for_each   = var.nodes
    name       = "sharednet1-${each.key}-mlops-${var.suffix}"
    network_id = data.openstack_networking_network_v2.sharednet1.id
    security_group_ids = [
      data.openstack_networking_secgroup_v2.allow_ssh.id,
      data.openstack_networking_secgroup_v2.allow_8000.id,
      data.openstack_networking_secgroup_v2.allow_8888.id,
      data.openstack_networking_secgroup_v2.allow_9090.id,
      data.openstack_networking_secgroup_v2.allow_3000.id
    ]
}

resource "openstack_networking_floatingip_v2" "floating_ip" {
  pool        = "public"
  description = "MLOps IP for ${var.suffix}"
  port_id     = openstack_networking_port_v2.sharednet1_ports["node1"].id
}