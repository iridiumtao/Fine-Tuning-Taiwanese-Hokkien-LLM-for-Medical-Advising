output "floating_ip_out" {
  description = "Floating IP assigned to node1"
  value       = openstack_networking_floatingip_v2.floating_ip.address
}

output "private_net_ports" {
  value = {
    for k, p in openstack_networking_port_v2.private_net_ports : k => p.id
  }
}

output "sharednet1_ports" {
  value = {
    for k, p in openstack_networking_port_v2.sharednet1_ports : k => p.id
  }
}