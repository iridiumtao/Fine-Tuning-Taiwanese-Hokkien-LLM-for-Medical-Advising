output "floating_ip_out" {
  description = "Floating IP assigned to node1"
  value       = openstack_networking_floatingip_v2.floating_ip.address
}

output "sharednet2_port_id" {
  value = openstack_networking_port_v2.sharednet2_port.id
}
