# Retail Branch WiFi Infrastructure with Ansible Lab

## Overview

This lab simulates the wired network infrastructure underlying a multi-SSID 
retail branch WiFi deployment — think Cisco Meraki APs on a Cisco switched 
network. The goal is to demonstrate practical Network Engineer skills including 
VLAN design, trunking, inter-VLAN routing, DHCP, ACL-based segmentation and 
STP in a documented, reproducible lab environment.

Built in Cisco Modeling Labs (CML) Free tier. No physical hardware required.
Ansible playbooks added later.

Related lab: [EVPN/VXLAN Spine-Leaf Fabric](https://github.com/hans375-olo/evpn-vxlan-lab--arista-eve-ng)

---

## Topology


```
                    ┌─────────────────┐
                    │       R1        │
                    │  IOS XE 17.16   │
                    │  10.10.x.1/24   │
                    │  (all VLANs)    │
                    └────────┬────────┘
                             │ Et0/0
                             │ trunk (10,20,30,99)
                             │ Et0/0
                    ┌────────┴────────┐
                    │      L3SW       │
                    │  IOS XE 17.16   │
                    │  10.10.99.2     │
                    │  STP Root       │
                    └──────┬──────┬───┘
                           │      │
              Et0/1        │      │ Et0/2
         trunk (10,20,30,99)      trunk (10,20,30,99)
                           │      │
               ┌───────────┘      └───────────┐
               │                              │
      ┌────────┴────────┐            ┌────────┴────────┐
      │      ACC1       │            │      ACC2       │
      │  IOS XE 17.16   │            │  IOS XE 17.16   │
      │  10.10.99.3     │            │  10.10.99.4     │
      └──┬───────────┬──┘            └──┬──────┬────┬──┘
         │           │                  │      │    │
       Et0/2       Et0/3              Et0/1  Et0/3  Et0/0
         │           │                  │      │    │
    [Meraki AP] [Meraki AP]        [Meraki AP] │  trunk
    AP-WING1-1  AP-WING1-2         AP-WING2-1  │  (10,20,30,99)
                                        [Meraki AP]  │
                                        AP-WING2-2   │
                                                ┌────┴────┐
                                                │ MGMT-PC │
                                                │ Alpine  │
                                                │10.10.99.10│
                                                └─────────┘

VLAN Summary:
┌──────┬──────────────┬─────────────────┬──────────────────────────────┐
│ VLAN │ Name         │ Subnet          │ Policy                       │
├──────┼──────────────┼─────────────────┼──────────────────────────────┤
│  10  │ Corporate    │ 10.10.10.0/24   │ Unrestricted                 │
│  20  │ Guest        │ 10.10.20.0/24   │ Internet only, isolated      │
│  30  │ IoT/Camera   │ 10.10.30.0/24   │ No Corporate, no Management  │
│  99  │ Management   │ 10.10.99.0/24   │ Infrastructure access only   │
└──────┴──────────────┴─────────────────┴──────────────────────────────┘

AP Uplink Trunk Policy:
┌─────────────────────────────────────────────────────────┐
│ Allowed VLANs:  10, 20, 30 (client SSIDs)              │
│ Native VLAN:    99 (AP management, untagged)            │
│ PortFast trunk: enabled (trusted device, fast bring-up) │
│ BPDU Guard:     disabled (AP compatibility)             │
└─────────────────────────────────────────────────────────┘

Traffic Flow Example:
  Guest WiFi client → Meraki AP (SSID tagged VLAN 20)
  → ACC trunk port → L3SW → R1 Et0/0.20
  → GUEST-OUT ACL applied → internet permitted
  → all internal VLANs denied
```

---

## Node List & Images

| Node | CML Image | IOS Version | Role |
|------|-----------|-------------|------|
| R1 | IOL | IOS XE 17.16.1a | Edge router, inter-VLAN routing, DHCP |
| L3SW | IOL-L2 | IOS XE 17.16.1a | Distribution switch, STP root |
| ACC1 | IOL-L2 | IOS XE 17.16.1a | Access switch, wing 1 |
| ACC2 | IOL-L2 | IOS XE 17.16.1a | Access switch, wing 2 |
| MGMT-PC | Alpine Linux | - | Management host, lab verification |

> **Note:** This lab uses CML Free tier (5-node maximum). IOL and IOL-L2 
> provide full IOS XE 17.16 CLI, making configs directly applicable to 
> real Cisco deployments.

---

## Step-by-Step Build

### 1. Base Configuration

All nodes configured with hostname, domain name (lab.local), local admin 
account (privilege 15), SSH v2 (RSA 2048-bit) and a management IP on VLAN 99.

Management IP assignments:

| Device | VLAN 99 IP |
|--------|------------|
| R1 | 10.10.99.1 |
| L3SW | 10.10.99.2 |
| ACC1 | 10.10.99.3 |
| ACC2 | 10.10.99.4 |
| MGMT-PC | 10.10.99.10 |

Example base config (R1):
```
hostname R1
ip domain-name lab.local
crypto key generate rsa modulus 2048
username admin privilege 15 secret cisco123
ip ssh version 2
line vty 0 4
 login local
 transport input ssh
interface Ethernet0/0
 description UPLINK-TO-L3SW
 no shutdown
interface Ethernet0/0.99
 encapsulation dot1Q 99
 ip address 10.10.99.1 255.255.255.0
 no shutdown
```

### 2. VLAN & Trunk Setup

VLANs 10, 20, 30, 99 created on all switches with descriptive names:
```
vlan 10
 name Corporate-POS
vlan 20
 name Guest
vlan 30
 name IoT-Camera
vlan 99
 name Management
```

All inter-switch links configured as 802.1Q trunks explicitly allowing 
VLANs 10, 20, 30, 99. Native VLAN left as VLAN 1 consistently across 
all trunks (no user traffic on VLAN 1):
```
interface Ethernet0/0
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk allowed vlan 10,20,30,99
```

R1 uplink configured as router-on-a-stick with one subinterface per VLAN:
```
interface Ethernet0/0.10
 encapsulation dot1Q 10
 ip address 10.10.10.1 255.255.255.0
interface Ethernet0/0.20
 encapsulation dot1Q 20
 ip address 10.10.20.1 255.255.255.0
interface Ethernet0/0.30
 encapsulation dot1Q 30
 ip address 10.10.30.1 255.255.255.0
interface Ethernet0/0.99
 encapsulation dot1Q 99
 ip address 10.10.99.1 255.255.255.0
```

MGMT-PC connects to ACC2 via a trunk port using a VLAN subinterface 
(eth0.99) to ensure correct VLAN tagging and keep the native VLAN 
consistent across all trunks.

### 3. DHCP

R1 acts as DHCP server for all four VLANs. First 10 addresses in each 
subnet reserved for network infrastructure:

```
ip dhcp excluded-address 10.10.10.1 10.10.10.10
ip dhcp excluded-address 10.10.20.1 10.10.20.10
ip dhcp excluded-address 10.10.30.1 10.10.30.10
ip dhcp excluded-address 10.10.99.1 10.10.99.10

ip dhcp pool Corporate-POS
 network 10.10.10.0 255.255.255.0
 default-router 10.10.10.1
 dns-server 8.8.8.8
 lease 0 8

ip dhcp pool Guest
 network 10.10.20.0 255.255.255.0
 default-router 10.10.20.1
 dns-server 8.8.8.8
 lease 0 4

ip dhcp pool IoT-Camera
 network 10.10.30.0 255.255.255.0
 default-router 10.10.30.1
 dns-server 8.8.8.8
 lease 0 8

ip dhcp pool Management
 network 10.10.99.0 255.255.255.0
 default-router 10.10.99.1
 dns-server 8.8.8.8
 lease 1
```

| Pool | Lease Time | Rationale |
|------|------------|-----------|
| Corporate-POS | 8 hours | Standard business day |
| Guest | 4 hours | Short lease for transient users |
| IoT-Camera | 8 hours | Relatively stable devices |
| Management | 24 hours | Infrastructure only |

### 4. Inter-VLAN Routing & ACLs

Inter-VLAN routing handled by R1 subinterfaces. Two ACLs enforce 
segmentation policy, applied inbound at the routing boundary:

```
ip access-list extended GUEST-OUT
 deny   ip 10.10.20.0 0.0.0.255 10.10.10.0 0.0.0.255
 deny   ip 10.10.20.0 0.0.0.255 10.10.30.0 0.0.0.255
 deny   ip 10.10.20.0 0.0.0.255 10.10.99.0 0.0.0.255
 permit ip any any

ip access-list extended IOT-OUT
 deny   ip 10.10.30.0 0.0.0.255 10.10.10.0 0.0.0.255
 deny   ip 10.10.30.0 0.0.0.255 10.10.99.0 0.0.0.255
 permit ip any any

interface Ethernet0/0.20
 ip access-group GUEST-OUT in

interface Ethernet0/0.30
 ip access-group IOT-OUT in
```

Segmentation policy summary:

| Source | Corporate | Guest | IoT | Management | Internet |
|--------|-----------|-------|-----|------------|---------|
| Corporate | yes | yes | yes | yes | yes |
| Guest | no | yes | no | no | yes |
| IoT | no | yes | yes | no | yes |
| Management | yes | yes | yes | yes | yes |

Design rationale: ACLs applied inbound at R1 subinterfaces keeps 
policy centralised and easy to audit. In a production deployment 
this would be replaced by zone-based firewall policy on a dedicated 
security appliance (Fortinet, Palo Alto).

### 5. STP

Rapid PVST+ running on all switches (default on IOL-L2). L3SW 
explicitly configured as root bridge for all VLANs:

```
spanning-tree vlan 1,10,20,30,99 root primary
```

PortFast enabled on all access-facing ports:
```
interface Ethernet0/0
 spanning-tree portfast
```

BPDU Guard enabled on access-facing ports (except AP uplinks):
```
interface Ethernet0/0
 spanning-tree bpduguard enable
```

### 6. AP Uplink Ports

Access switches pre-configured with trunk ports simulating Cisco 
Meraki AP uplinks. In a production deployment each AP uplink carries 
multiple SSIDs mapped to VLANs:

| SSID | VLAN | Subnet |
|------|------|--------|
| Corporate | 10 | 10.10.10.0/24 |
| Guest | 20 | 10.10.20.0/24 |
| IoT/Camera | 30 | 10.10.30.0/24 |

AP uplink port config (same on all four AP-facing ports):
```
interface Ethernet0/2
 description AP-UPLINK-WING1-1
 switchport trunk encapsulation dot1q
 switchport mode trunk
 switchport trunk allowed vlan 10,20,30
 switchport trunk native vlan 99
 spanning-tree portfast trunk
 no shutdown
```

AP uplink design decisions:
- VLANs 10, 20, 30 allowed — client SSIDs only
- Native VLAN 99 — AP receives management IP untagged, keeping it 
  on the management plane without exposing VLAN 99 to clients
- PortFast trunk enabled — APs are trusted devices, fast port 
  transition appropriate, no need to wait for STP convergence on reboot
- BPDU Guard disabled — some AP models pass BPDUs and would 
  otherwise trigger an err-disable

Port assignments:

| Switch | Port | Description |
|--------|------|-------------|
| ACC1 | Ethernet0/2 | AP-UPLINK-WING1-1 |
| ACC1 | Ethernet0/3 | AP-UPLINK-WING1-2 |
| ACC2 | Ethernet0/1 | AP-UPLINK-WING2-1 |
| ACC2 | Ethernet0/3 | AP-UPLINK-WING2-2 |

Simulation boundary: this lab covers the wired infrastructure only. 
No wireless controller or AP images are used. The AP uplink ports 
demonstrate correct trunk configuration for a multi-SSID deployment. 
The ACL and DHCP policies apply to all clients regardless of whether 
they connect via wire or WiFi — the enforcement point is R1, not the AP.

SSID to VLAN mapping in a Cisco Meraki deployment is configured in 
the Meraki dashboard per SSID. The AP uplink port on the switch must 
trunk the corresponding VLAN to the AP. No additional switch 
configuration is required beyond what is implemented in this lab.

---

## Verification

### Management plane
```
! From MGMT-PC (10.10.99.10), all should reply
ping 10.10.99.1   (R1)
ping 10.10.99.2   (L3SW)
ping 10.10.99.3   (ACC1)
ping 10.10.99.4   (ACC2)
```

### DHCP
```
R1# show ip dhcp binding
R1# show ip dhcp pool
R1# show ip dhcp conflict
```

### ACL verification
```
R1# show ip access-lists
```
Deny counters increment when simulating Guest or IoT source traffic 
toward blocked destinations. Permit counters reflect allowed traffic.

### STP
```
! On all switches
show spanning-tree summary
show spanning-tree vlan 10
```
Expected: L3SW as root for all user VLANs, no blocked ports 
(star topology, no redundant links).

### Trunks
```
! On all switches
show interfaces trunk
show vlan brief
```
Expected: VLANs 10, 20, 30, 99 active and forwarding on all trunk ports.

### AP uplink ports
```
! On ACC1 and ACC2
show interfaces trunk
show spanning-tree interface Ethernet0/2 portfast
```
Expected: AP uplink ports trunking VLANs 10, 20, 30 with native VLAN 
99, PortFast trunk enabled.

---

## Known Limitations

**Single NIC MAC duplication**
MGMT-PC uses a single physical NIC (eth0) with VLAN subinterfaces 
for lab verification. This causes the same MAC address to appear in 
multiple VLANs in the switch MAC address table, resulting in frame 
duplication when simulating inter-VLAN traffic from the same host. 
In production each client has a unique MAC per VLAN. This does not 
affect the validity of ACL or routing verification — deny counters 
behave correctly.

**Native VLAN 1 STP isolation**
VLAN 1 is not included in trunk allowed lists (by design — no user 
traffic on VLAN 1). STP BPDUs for VLAN 1 do not propagate between 
switches, causing each switch to independently claim root for VLAN 1. 
This is a lab artefact with no operational impact.

**No upstream internet connectivity**
R1 has no default route to an upstream provider. Guest and IoT 
internet access is implied by the permit-any ACL entries but not 
functional in this lab. See Extending the Lab for how to connect 
to your physical network via CML External Connector.

**CML Free tier node limit**
Maximum 5 nodes constrains the topology. A production deployment 
would add redundant uplinks, a dedicated firewall, separate DHCP 
and DNS servers, and a wireless controller.

**Alpine network config persistence**
Alpine Linux in CML does not persist network configuration across 
reboots unless written to /etc/network/interfaces. The DHCP client 
runs by default on boot. Static VLAN subinterface config must be 
written explicitly:

```
# /etc/network/interfaces
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet manual

auto eth0.99
iface eth0.99 inet static
  address 10.10.99.10
  netmask 255.255.255.0
  gateway 10.10.99.1
  vlan-raw-device eth0
```
**IOL-L2 boots with `ip routing` enabled**
IOL-L2 images enable IP routing by default. On a switch this means the
device will attempt to route traffic independently rather than rely on R1,
breaking SSH reachability from the management network. All switch configs
include `no ip routing`. If reachability issues occur after a fresh boot,
verify with `show ip routing` on the switch console and apply
`no ip routing` manually before retrying the playbook.

---

## Extending the Lab

### Phase 2 — Wireless Controller Integration
Add a Cisco Catalyst 9800 wireless controller (if available in your 
CML version) or connect to a cloud-managed Meraki environment:

- 9800 WLC manages AP registration and SSID-to-VLAN mapping
- APs connect to the pre-configured uplink trunk ports on ACC1/ACC2
- SSID broadcast begins immediately — wired policy already in place

### Phase 3 — Stateful Firewall
Replace R1 ACLs with a Fortinet or Palo Alto VM between the 
distribution layer and the edge:

- Zone-based policy instead of interface ACLs
- Deep packet inspection for IoT and Guest traffic
- Application-aware Guest filtering (social media, streaming, etc.)
- This lab provides direct preparation for Fortinet NSE certification

### Phase 4 — Automation
&
### Phase 5 — External Connector (CML)
Phases 4 and 5 are implemented together because they depend on each other:
external connectivity is what makes host-based automation possible, and
host-based automation is the reason external connectivity is worth configuring.

### Network path

```
Lab nodes (10.10.99.x)
  → R1 Et0/1 (192.168.255.2)
    → CML External Connector → virbr0 (192.168.255.1) on Ubuntu/CML host
      → bridge0 (172.20.1.10) on Ubuntu/CML host
        → Fedora Ansible VM (172.20.1.x) — campus LAN, bridged mode
```

The CML External Connector bridges R1 Et0/1 into `virbr0`, a libvirt bridge
managed by CML on the Ubuntu host. A tap interface (visible as `lnk*` in
`ip addr`) is created per External Connector link and enslaved to `virbr0`.

R1 holds a default route via 192.168.255.1. The Fedora VM holds a static
route to 10.10.99.0/24 via the Ubuntu host's campus LAN address:

```bash
# On Fedora — persistent static route (NetworkManager)
sudo nmcli connection modify <connection-name> \
  +ipv4.routes "10.10.99.0/24 172.20.1.10"
sudo nmcli connection up <connection-name>
```

Both VMs run in VMware Workstation bridged mode, placing them on the same
172.20.1.0/24 campus LAN segment. Ansible reaches lab nodes directly over
SSH — no jump host required.

Return path: lab nodes reply via R1's default route (192.168.255.1 →
Ubuntu virbr0 → bridge0 → campus LAN → Fedora VM).

### Why host-based automation matters

Running the control node outside CML mirrors how automation works in
production:

- The management plane is physically separate from the network under test
- Ansible state, playbooks, logs, and Git history persist across CML
  restarts and topology changes
- The External Connector path exercises the same SSH reachability a real
  out-of-band management network would use
- Any VM or tool on the same management network can be added without
  touching the lab topology

### Repository structure

```
retail-branch-wifi-ansible-lab/
├── ansible/
│   ├── ansible.cfg                 # vault password file path, default inventory
│   ├── inventory/
│   │   ├── hosts.ini               # device inventory
│   │   └── group_vars/
│   │       └── all.yml             # connection vars + credentials, Vault-encrypted
│   ├── playbooks/
│   │   ├── push_base_configs.yml   # idempotent full config push
│   │   └── backup_configs.yml      # pull running configs to Fedora
│   └── requirements.yml            # Ansible collection dependencies
├── backups/
│   ├── latest/                     # overwritten each run — diff baseline
│   └── archive/                    # timestamped — audit trail
├── verification/
│   └── assert_lab_state.py         # Netmiko state assertions
├── topology.yaml                   # CML topology export — import to recreate lab
└── README.md
```

### Ansible Vault — credential management

All connection vars and credentials live in a single file,
`inventory/group_vars/all.yml`, which is encrypted with Ansible Vault.
This is simpler than splitting plain-text and encrypted files, and avoids
a subtle Ansible variable resolution issue where `{{ vault_* }}` references
in a plain-text `all.yml` can remain unresolved if the vault file is loaded
after variable interpolation occurs.

`inventory/group_vars/all.yml` (shown unencrypted — always encrypted at rest):

```yaml
ansible_connection: ansible.netcommon.network_cli
ansible_network_os: cisco.ios.ios
ansible_user: admin
ansible_password: cisco123
ansible_become: true
ansible_become_method: enable
ansible_become_password: cisco123
ansible_ssh_common_args: "-o StrictHostKeyChecking=no"
```

Encrypt it:

```bash
ansible-vault encrypt inventory/group_vars/all.yml
```

Store the vault password in a local file excluded from Git — this means
`ansible-playbook` never prompts for a password:

```bash
echo "your-vault-password" > ~/.vault_pass
chmod 600 ~/.vault_pass
echo ".vault_pass" >> ~/.gitignore
```

Point `ansible.cfg` to it:

```ini
# ansible/ansible.cfg
[defaults]
vault_password_file = ~/.vault_pass
inventory = inventory/hosts.ini
```

All `ansible-playbook` runs now decrypt transparently. To edit credentials:

```bash
ansible-vault edit inventory/group_vars/all.yml
```

> **Production note:** In production you would split this into a plain-text
> file for non-sensitive connection vars and a separate encrypted vault file
> for credentials only — keeping the inventory human-readable without the
> vault password. For a lab of this size the single encrypted file is
> simpler and avoids variable resolution edge cases.

### Ansible — base config push

`playbooks/push_base_configs.yml` uses IOS resource modules for idempotent
state management, falling back to `ios_config` only for constructs not
covered by a dedicated module:

| Play | Module | Purpose |
|------|--------|---------|
| switches | `cisco.ios.ios_vlans` | VLAN database, `state: merged` |
| switches | `cisco.ios.ios_l2_interfaces` | Trunk port config, `state: merged` |
| switches | `cisco.ios.ios_config` | STP root (L3SW only) |
| routers | `cisco.ios.ios_config` | Subinterfaces, ACLs, ACL application |

Trunk port assignments are defined as a dict in playbook vars keyed by
`inventory_hostname`, keeping the playbook self-contained without
requiring per-host `host_vars` files for a lab of this size.

Run from the `ansible/` directory:

```bash
cd ~/cml-lab1/ansible
ansible-playbook playbooks/push_base_configs.yml
```

### Ansible — backup playbook

`playbooks/backup_configs.yml` pulls the running config from all four
nodes and writes it to two locations on the Fedora VM:

- `backups/latest/<hostname>.cfg` — overwritten on every run, used as
  the baseline for config diff
- `backups/archive/<hostname>_<timestamp>.cfg` — never overwritten,
  provides a full audit trail


## cat ~/cml-lab1/ansible/playbooks/backup_configs.yml

```yaml
---
- name: Backup running configs from all nodes
  hosts: all
  gather_facts: false

  vars:
    backup_dir: "{{ playbook_dir }}/../backups"
    timestamp: "{{ lookup('pipe', 'date +%Y-%m-%dT%H-%M') }}"

  tasks:
    - name: Collect running config
      cisco.ios.ios_command:
        commands: show running-config
      register: running_config

    - name: Ensure backup directories exist
      ansible.builtin.file:
        path: "{{ item }}"
        state: directory
        mode: "0750"
      loop:
        - "{{ backup_dir }}/latest"
        - "{{ backup_dir }}/archive"
      delegate_to: localhost
      run_once: false

    - name: Write latest config (overwrite)
      ansible.builtin.copy:
        content: "{{ running_config.stdout[0] }}"
        dest: "{{ backup_dir }}/latest/{{ inventory_hostname }}.cfg"
        mode: "0640"
      delegate_to: localhost

    - name: Write timestamped archive copy
      ansible.builtin.copy:
        content: "{{ running_config.stdout[0] }}"
        dest: "{{ backup_dir }}/archive/{{ inventory_hostname }}_{{ timestamp }}.cfg"
        mode: "0640"
      delegate_to: localhost
```

Run:

```bash
ansible-playbook playbooks/backup_configs.yml
```

After a clean lab build, run this immediately to establish the baseline.
To diff the current state against baseline at any point:

```bash
diff backups/latest/R1.cfg <(ssh admin@10.10.99.1 "show run")
# or re-run the backup playbook and use git diff:
git diff backups/latest/ backups/archive
# if you have not before make sure to install git first
# on Fedora:
sudo dnf install git
```

Committing `backups/latest/` to Git after the initial build means every
subsequent backup run produces a clean `git diff` showing exactly what
changed — the same workflow used in production network change management.

> **Note:** Add `backups/archive/` to `.gitignore` to keep the repo clean.
> Only `backups/latest/` needs version control.

### Netmiko — state verification

`verification/assert_lab_state.py` connects to each node over SSH,
runs show commands, and asserts expected state. Exits 0 on full pass,
1 on any failure — usable as a CI step or a post-change check.

Assertions covered:

| Device | Checks |
|--------|--------|
| R1 | Subinterfaces up (all 4 VLANs), ACLs exist with deny entries, ACLs applied inbound on correct subinterfaces, DHCP pools present |
| L3SW | VLAN database, trunk allowed VLANs, trunk forwarding state, STP root |
| ACC1/ACC2 | VLAN database, trunk allowed VLANs, trunk forwarding state, not STP root |

Run:

```bash
python3 verification/assert_lab_state.py
```

---

## Quickstart — Recreating the Lab

This guide assumes:
- CML instance running on an Ubuntu VM (VMware, bridged)
- Fedora VM running on the same host (VMware, bridged)
- Both VMs on the same LAN segment
- The `topology.yaml` file from this repository

### 1. Import the CML topology

In the CML web UI: **Import** → select `topology.yaml` from the repo.
This creates all four nodes (R1, L3SW, ACC1, ACC2) with interfaces
pre-wired and the External Connector linked to R1 Et0/1.

Start the lab. Wait for all nodes to reach **BOOTED** state before
proceeding.

> **IOL-L2 gotcha — `no ip routing`:** IOL-L2 images boot with
> `ip routing` enabled by default. This causes the switches to attempt
> to route traffic themselves, breaking SSH reachability from the Fedora
> VM to switch management IPs. The symptom is a silent SSH timeout.
>
> The pushed configs include `no ip routing` on all three switches.
> If you connect to a switch console before running the playbook and
> SSH is unreachable, confirm with `show ip routing` and apply
> `no ip routing` manually to unblock the push.

### 2. Set up the Fedora control node

```bash
# Install Ansible
sudo dnf install ansible-core python3-pip -y

# Install required collections
ansible-galaxy collection install -r requirements.yml

# Install Netmiko for the verification script
pip3 install netmiko --user
```

`requirements.yml`:

```yaml
collections:
  - name: cisco.ios
  - name: ansible.netcommon
```

### 3. Configure network reachability

Add a static route on Fedora so it can reach the lab management subnet
via the Ubuntu/CML host:

```bash
sudo nmcli connection modify <your-connection-name> \
  +ipv4.routes "10.10.99.0/24 <ubuntu-host-172.20.1.x>"
sudo nmcli connection up <your-connection-name>
```

Verify:

```bash
ping 10.10.99.1   # R1 — should reply once configs are pushed
```

### 4. Configure Ansible Vault

```bash
# Edit all.yml with your credentials (already present in the repo as encrypted)
# To re-encrypt with your own password:
ansible-vault decrypt ansible/inventory/group_vars/all.yml
# edit if needed, then re-encrypt:
ansible-vault encrypt ansible/inventory/group_vars/all.yml

# Store the vault password locally so you're never prompted
echo "your-vault-password" > ~/.vault_pass
chmod 600 ~/.vault_pass
# .vault_pass is already in .gitignore
```

### 5. Push base configuration

```bash
ansible-playbook playbooks/push_base_configs.yml
```

Expected: all tasks complete with `ok` or `changed`, no failures.

### 6. Establish config baseline

```bash
ansible-playbook playbooks/backup_configs.yml
git add backups/latest/
git commit -m "baseline: initial lab build"
```

### 7. Verify lab state

```bash
python3 verification/assert_lab_state.py
```

Expected: all assertions `[PASS]`, exit 0.

The lab is fully operational when the verification script exits clean.
Any future change can be validated by re-running steps 6 and 7 and
inspecting the `git diff`.

---

## Lessons Learned

- IOL and IOL-L2 in CML Free provide full IOS XE 17.16 — more capable 
  than expected for a free tier and directly applicable to real deployments
- Consistent native VLAN across all trunks is critical — mixing native 
  VLANs causes subtle frame duplication and is a known VLAN hopping 
  attack vector
- ACLs applied inbound at the routing boundary are easier to reason 
  about and audit than distributed switch ACLs
- Alpine Linux in CML requires manual persistence of network config 
  to /etc/network/interfaces — DHCP client runs by default on boot
- A single-NIC management host with VLAN subinterfaces is sufficient 
  for lab verification but introduces MAC table ambiguity across VLANs
- PortFast trunk on AP uplinks is appropriate and necessary — without 
  it APs experience a 30-second delay on every reboot while STP converges
- BPDU Guard should not be enabled on AP uplinks — some AP models 
  pass BPDUs and will trigger err-disable on the port
- IOL-L2 requires explicit `no ip routing` — the default routing-enabled
  state silently breaks SSH reachability from the management network before
  configs are pushed; always verify on the console first if the initial
  playbook run fails
- Encrypt the entire `group_vars/all.yml` rather than splitting into plain-text
  and vault files — the two-file pattern is cleaner in theory but causes a
  variable resolution edge case where `{{ vault_* }}` references remain
  unresolved if the vault file is loaded after interpolation; a single
  encrypted file sidesteps this entirely
- Store the vault password in `~/.vault_pass` (chmod 600, in `.gitignore`)
  and point `ansible.cfg` to it — eliminates the `--ask-vault-pass` prompt
  on every run without exposing credentials
- `backups/latest/` committed to Git after the initial build turns every
  subsequent backup run into a meaningful `git diff` — the same change
  management pattern used in production
- ACL lines pushed via `ios_config` require correct leading whitespace —
  IOS XE is sensitive to indentation inside named ACL blocks; a missing
  space before `deny`/`permit` produces a new top-level config statement
  rather than an ACL entry
- `ios_vlans` and `ios_l2_interfaces` with `state: merged` are idempotent
  — re-running the playbook on an already-configured switch produces only
  `ok`, never spurious `changed` — use resource modules over raw
  `ios_config` wherever a module exists

~~~
