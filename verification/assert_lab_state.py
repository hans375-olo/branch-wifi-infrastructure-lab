"""
Retail Branch WiFi Lab — state verification script.
Connects to each lab node over SSH via VLAN 99 (management plane),
runs show commands, and asserts expected state.

Exit 0 = all assertions passed.
Exit 1 = one or more assertions failed.
"""

import sys
from netmiko import ConnectHandler

CREDENTIALS = {
    "device_type": "cisco_ios",
    "username": "admin",
    "password": "cisco123",
    "secret": "cisco123",
}

DEVICES = {
    "R1":   "10.10.99.1",
    "L3SW": "10.10.99.2",
    "ACC1": "10.10.99.3",
    "ACC2": "10.10.99.4",
}

EXPECTED_VLANS       = ["10", "20", "30", "99"]
EXPECTED_TRUNK_VLANS = "10,20,30,99"
EXPECTED_ACLS        = ["GUEST-OUT", "IOT-OUT"]

failures = []


def check(condition: bool, description: str) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {description}")
    if not condition:
        failures.append(description)


def connect(host: str) -> ConnectHandler:
    return ConnectHandler(**CREDENTIALS, host=host)


def verify_router() -> None:
    print(f"\n--- R1 ({DEVICES['R1']}) ---")
    with connect(DEVICES["R1"]) as net:
        net.enable()

        # Subinterfaces up
        int_brief = net.send_command("show ip interface brief")
        for vlan in EXPECTED_VLANS:
            subint = f"Ethernet0/0.{vlan}"
            # Grab the status field from the line for this subinterface
            line = [l for l in int_brief.splitlines() if subint in l]
            up = bool(line) and "up" in line[0].lower()
            check(up, f"{subint} is up")

        # ACLs exist and contain deny entries
        acl_output = net.send_command("show ip access-lists")
        for acl in EXPECTED_ACLS:
            check(acl in acl_output, f"ACL {acl} exists")
            if acl in acl_output:
                section = acl_output.split(acl)[1][:400]
                check("deny" in section, f"ACL {acl} contains deny entries")

        # ACLs applied inbound on correct subinterfaces
        for vlan, acl in [("20", "GUEST-OUT"), ("30", "IOT-OUT")]:
            detail = net.send_command(f"show ip interface Ethernet0/0.{vlan}")
            check(
                acl in detail and "inbound" in detail.lower(),
                f"{acl} applied inbound on Ethernet0/0.{vlan}",
            )

        # DHCP pools
        dhcp_output = net.send_command("show ip dhcp pool")
        for pool in ["Corporate-POS", "Guest", "IoT-Camera", "Management"]:
            check(pool in dhcp_output, f"DHCP pool '{pool}' exists")


def verify_switches() -> None:
    switch_devices = {k: v for k, v in DEVICES.items() if k != "R1"}
    for name, host in switch_devices.items():
        print(f"\n--- {name} ({host}) ---")
        with connect(host) as net:
            net.enable()

             # VLAN database
            vlan_brief = net.send_command("show vlan brief")
            for vlan in EXPECTED_VLANS:
                vlan_line = next(
        (line for line in vlan_brief.splitlines() if line.startswith(vlan + " ") or line.startswith(vlan + "\t")),
                    None
                 )   
            present = vlan_line is not None and "active" in vlan_line
            check(present, f"VLAN {vlan} present and active") 
                      
            # Trunk config and forwarding state
            trunk_output = net.send_command("show interfaces trunk")
            check(
                EXPECTED_TRUNK_VLANS in trunk_output,
                f"Trunk allows VLANs {EXPECTED_TRUNK_VLANS}",
            )
            check(
                "forwarding" in trunk_output.lower(),
                "At least one trunk port forwarding",
            )

            # STP root assertion
            stp_output = net.send_command("show spanning-tree vlan 10")
            is_root = "This bridge is the root" in stp_output
            if name == "L3SW":
                check(is_root, "L3SW is STP root for VLAN 10")
            else:
                check(not is_root, f"{name} is not STP root for VLAN 10 (correct)")


def main() -> None:
    print("=" * 56)
    print("Retail Branch WiFi Lab — state verification")
    print("=" * 56)

    verify_router()
    verify_switches()

    print("\n" + "=" * 56)
    if failures:
        print(f"RESULT: {len(failures)} assertion(s) FAILED:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("RESULT: All assertions PASSED.")
        sys.exit(0)


if __name__ == "__main__":
    main()
