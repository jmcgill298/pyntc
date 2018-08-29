class EOSData:

    vendor = 'arista'
    model = 'vEOS'
    os_version = '4.16.9M-3799680.4169M'
    image_name = '/vEOS-lab.swi'
    hostname = 'cer-arista'
    fqdn = 'cer-arista'
    uptime = 389820
    interface_list = ['Ethernet1', 'Ethernet2', 'Ethernet3', 'Management1']
    interface_status_list = [
        {'description': '', 'duplex': 'duplexFull', 'interface': 'Management1',
         'speed': 1000000000, 'state': 'connected', 'vlan': None},
        {'description': '', 'duplex': 'duplexFull', 'interface': 'Ethernet2',
         'speed': 0, 'state': 'connected', 'vlan': 1},
        {'description': '', 'duplex': 'duplexFull', 'interface': 'Ethernet3',
         'speed': 0, 'state': 'connected', 'vlan': 1},
        {'description': '', 'duplex': 'duplexFull', 'interface': 'Ethernet1',
         'speed': 0, 'state': 'connected', 'vlan': None},
    ]
    vlan_list = ['1']


class IOSData:

    vendor = 'cisco'
    model = 'WS-C3650-48PQ'
    os_version = '16.5.1a'
    image_name = 'cat3k_caa-universalk9.16.05.01a.SPA.bin'
    config_register = '0x102'
    hostname = 'C3650-2'
    fqdn = 'N/A'
    uptime = '2 weeks, 4 days, 12 hours, 17 minutes'
    interface_list = ['Vlan1', 'GigabitEthernet0/0'] + ['GigabitEthernet1/0/{}'.format(intf) for intf in range(1,49)] \
                     + ['Te1/1/{}'.format(intf) for intf in range(1,5)] + ['Loopback0']
    interface_status_list = [
        {'description': '', 'duplex': 'duplexFull', 'interface': 'Management1',
         'speed': 1000000000, 'state': 'connected', 'vlan': None},
        {'description': '', 'duplex': 'duplexFull', 'interface': 'Ethernet2',
         'speed': 0, 'state': 'connected', 'vlan': 1},
        {'description': '', 'duplex': 'duplexFull', 'interface': 'Ethernet3',
         'speed': 0, 'state': 'connected', 'vlan': 1},
        {'description': '', 'duplex': 'duplexFull', 'interface': 'Ethernet1',
         'speed': 0, 'state': 'connected', 'vlan': None},
    ]
    vlan_list = ['1', '10', '20', '30', '40', '60', '70', '100', '133', '1002', '1003', '1004', '1005']
