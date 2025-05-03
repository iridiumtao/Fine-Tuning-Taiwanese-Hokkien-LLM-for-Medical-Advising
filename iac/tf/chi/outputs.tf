output "floating_ip_out" {
  description = "Floating IP assigned to node1"
  value       = openstack_networking_floatingip_v2.floating_ip.address
}

output "sharednet1_port_id_node1" {
  value = openstack_networking_port_v2.sharednet1_ports["node1"].id
}