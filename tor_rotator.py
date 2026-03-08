#!/usr/bin/env python3
"""
TOR-LIKE IP ROTATION ENGINE
Simulates Tor Browser's circuit-based IP rotation mechanism

Features:
- 3-relay circuit architecture (Entry → Middle → Exit)
- Automatic rotation every N seconds
- Manual "New Identity" trigger (press ENTER)
- Circuit state tracking and termination
- Live dashboard with relay path visualization
"""

import time
import random
import threading
import sys
from scapy.all import IP, ICMP, send

# ========================
# CIRCUIT ARCHITECTURE
# ========================

class Circuit:
    """
    Represents a Tor-like circuit with 3 relay nodes.
    Only the exit node IP is visible to the destination.
    """
    def __init__(self):
        self.id = self._generate_circuit_id()
        self.created_at = time.time()
        
        # 3-hop relay chain (like real Tor)
        self.entry_node = self._generate_random_ip()
        self.middle_node = self._generate_random_ip()
        self.exit_node = self._generate_random_ip()
        
        self.packets_sent = 0
        self.active = True
    
    def _generate_circuit_id(self):
        """Generate unique circuit identifier"""
        return f"CIRCUIT-{random.randint(1000, 9999)}"
    
    def _generate_random_ip(self):
        """Generate random IP address for relay nodes"""
        return f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,255)}"
    
    def get_exit_ip(self):
        """Return the exit node IP (what target sees)"""
        return self.exit_node
    
    def get_relay_path(self):
        """Return formatted relay path"""
        return f"{self.entry_node} → {self.middle_node} → {self.exit_node}"
    
    def get_relay_path_short(self):
        """Return compact relay path for display"""
        return f"{self.entry_node[:12]}→{self.middle_node[:12]}→{self.exit_node[:12]}"
    
    def terminate(self):
        """Mark circuit as terminated (like Tor's circuit cleanup)"""
        self.active = False
        lifetime = time.time() - self.created_at
        print(f"\n[*] Circuit {self.id} terminated after {lifetime:.1f}s ({self.packets_sent} packets)")


# ========================
# STATE MANAGEMENT
# ========================

class RotationState:
    """
    Manages circuit rotation and packet sending state
    Similar to Tor's circuit manager
    """
    def __init__(self, target_ip, rotation_interval=5):
        self.target_ip = target_ip
        self.rotation_interval = rotation_interval
        self.current_circuit = Circuit()
        self.circuit_history = []
        self.running = True
        self.total_packets = 0
        self.total_circuits = 1
    
    def rotate(self):
        """
        Build new circuit and terminate old one
        This is the "New Identity" mechanism
        """
        # Terminate old circuit (critical Tor behavior)
        if self.current_circuit:
            self.current_circuit.terminate()
            self.circuit_history.append(self.current_circuit)
        
        # Build new circuit
        self.current_circuit = Circuit()
        self.total_circuits += 1
        
        print(f"[+] NEW CIRCUIT BUILT: {self.current_circuit.id}")
        print(f"[+] Relay Path: {self.current_circuit.get_relay_path()}")
        print(f"[+] Exit Node (Target sees): {self.current_circuit.get_exit_ip()}\n")
        
        return self.current_circuit
    
    def get_statistics(self):
        """Return session statistics"""
        return {
            'total_packets': self.total_packets,
            'total_circuits': self.total_circuits,
            'current_circuit_id': self.current_circuit.id,
            'current_circuit_packets': self.current_circuit.packets_sent
        }


# ========================
# WORKER THREADS
# ========================

def packet_sender(state):
    """
    Background worker: Continuously sends packets using current circuit's exit node
    """
    while state.running:
        try:
            # Use exit node IP (what target will see)
            exit_ip = state.current_circuit.get_exit_ip()
            
            # Construct and send packet
            packet = IP(src=exit_ip, dst=state.target_ip) / ICMP()
            send(packet, verbose=False)
            
            # Update counters
            state.current_circuit.packets_sent += 1
            state.total_packets += 1
            
            time.sleep(0.1)  # Fast fire rate
            
        except Exception as e:
            print(f"\n[!] Error sending packet: {e}")
            time.sleep(0.5)


def manual_rotation_listener(state):
    """
    Listens for ENTER key to trigger immediate circuit rotation
    Like Tor's "New Identity" button
    """
    print("[*] TIP: Press ENTER anytime for instant circuit rotation (Manual Identity Refresh)\n")
    
    while state.running:
        try:
            input()  # Blocks until user presses ENTER
            if state.running:
                old_circuit_id = state.current_circuit.id
                state.rotate()
                print(f"[!] MANUAL ROTATION TRIGGERED: {old_circuit_id} destroyed\n")
        except:
            break


def countdown_timer(state):
    """
    Foreground worker: Handles automatic rotation and live dashboard display
    """
    # Dashboard Header
    print("\n" + "=" * 130)
    print(f"{'LIVE CIRCUIT DASHBOARD':^130}")
    print("=" * 130)
    sys.stdout.write(f"{'TIME':<8} | {'CIRCUIT ID':<15} | {'RELAY PATH (Entry→Middle→Exit)':<52} | {'TARGET':<15} | {'PKTS':<6} | {'STATUS':<18}\n")
    sys.stdout.write("-" * 130 + "\n")
    
    start_time = time.time()
    
    try:
        while state.running:
            # Calculate remaining time
            elapsed = time.time() - start_time
            remaining = state.rotation_interval - elapsed
            
            # Format current time
            current_time_str = time.strftime("%H:%M:%S", time.localtime())
            
            if remaining <= 0:
                # Time's up! Rotate circuit
                circuit = state.current_circuit
                relay_path = circuit.get_relay_path_short()
                
                # Print final state before rotation
                sys.stdout.write(f"\r{current_time_str:<8} | {circuit.id:<15} | {relay_path:<52} | {state.target_ip:<15} | {circuit.packets_sent:<6} | {'ROTATING NOW':<18}\n")
                sys.stdout.flush()
                
                # Rotate to new circuit
                state.rotate()
                start_time = time.time()
                
            else:
                # Update live status row
                circuit = state.current_circuit
                relay_path = circuit.get_relay_path_short()
                status_msg = f"Active ({remaining:.1f}s)"
                
                sys.stdout.write(f"\r{current_time_str:<8} | {circuit.id:<15} | {relay_path:<52} | {state.target_ip:<15} | {circuit.packets_sent:<6} | {status_msg:<18}")
                sys.stdout.flush()
            
            time.sleep(0.1)  # Smooth countdown updates
    
    except KeyboardInterrupt:
        state.running = False
        print("\n\n[*] Shutdown initiated...")


# ========================
# MAIN PROGRAM
# ========================

def print_banner():
    """Display program banner"""
    print("\n" + "=" * 130)
    print(f"{'TOR-LIKE IP ROTATION ENGINE':^130}")
    print(f"{'Circuit-Based Identity Refresh System':^130}")
    print("=" * 130)
    print()


def print_statistics(state):
    """Display session statistics"""
    stats = state.get_statistics()
    print("\n" + "=" * 130)
    print(f"{'SESSION STATISTICS':^130}")
    print("=" * 130)
    print(f"Total Circuits Built: {stats['total_circuits']}")
    print(f"Total Packets Sent: {stats['total_packets']}")
    print(f"Average Packets per Circuit: {stats['total_packets'] / stats['total_circuits']:.0f}")
    print("=" * 130 + "\n")


def main():
    print_banner()
    
    # User configuration
    target = input("Enter Target IP (Default: 8.8.8.8): ").strip() or "8.8.8.8"
    
    try:
        interval_input = input("Enter rotation interval in seconds (Default: 5): ").strip()
        rotation_interval = float(interval_input) if interval_input else 5.0
    except ValueError:
        print("[!] Invalid interval, defaulting to 5 seconds")
        rotation_interval = 5.0
    
    # Initialize State
    state = RotationState(target, rotation_interval)
    
    print(f"\n[*] Target: {target}")
    print(f"[*] Rotation Interval: {rotation_interval} seconds")
    print(f"[*] Initial Circuit: {state.current_circuit.id}")
    print(f"[*] Relay Path: {state.current_circuit.get_relay_path()}")
    print(f"[*] Threading Engine: ACTIVE\n")
    
    # Start packet sender thread
    sender_thread = threading.Thread(target=packet_sender, args=(state,))
    sender_thread.daemon = True
    sender_thread.start()
    
    # Start manual rotation listener thread
    manual_thread = threading.Thread(target=manual_rotation_listener, args=(state,))
    manual_thread.daemon = True
    manual_thread.start()
    
    # Start countdown timer (main thread)
    try:
        countdown_timer(state)
    except KeyboardInterrupt:
        print("\n\n[!] Stopping Engine...")
        state.running = False
        sender_thread.join(timeout=1)
        manual_thread.join(timeout=1)
        
        # Show final statistics
        print_statistics(state)
        print("[*] Engine stopped successfully.")


if __name__ == "__main__":
    main()
