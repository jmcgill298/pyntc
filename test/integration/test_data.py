class EOSData:

    vendor = 'arista'
    model = 'vEOS'
    os_version = '4.16.9M-3799680.4169M'
    image_name = '/vEOS-lab.swi'
    hostname = 'cer-arista'
    fqdn = 'cer-arista'
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
