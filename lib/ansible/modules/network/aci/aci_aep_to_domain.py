#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2017, Dag Wieers <dag@wieers.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
module: aci_aep_to_domain
short_description: Bind AEPs to Physical or Virtual Domains on Cisco ACI fabrics (infra:RsDomP)
description:
- Bind AEPs to Physical or Virtual Domains on Cisco ACI fabrics.
- More information from the internal APIC class
  I(infra:RsDomP) at U(https://developer.cisco.com/site/aci/docs/apis/apic-mim-ref/).
author:
- Dag Wieers (@dagwieers)
version_added: '2.5'
notes:
- The C(aep) and C(domain) parameters should exist before using this module.
  The M(aci_aep) and M(aci_domain) can be used for these.
options:
  aep:
    description:
    - The name of the Attachable Access Entity Profile.
    aliases: [ aep_name ]
  domain:
    description:
    - Name of the physical or virtual domain being associated with the AEP.
    aliases: [ domain_name, domain_profile ]
  domain_type:
    description:
    - Determines if the Domain is physical (phys) or virtual (vmm).
    choices: [ phys, vmm ]
    aliases: [ type ]
  state:
    description:
    - Use C(present) or C(absent) for adding or removing.
    - Use C(query) for listing an object or multiple objects.
    choices: [ absent, present, query ]
    default: present
  vm_provider:
    description:
    - The VM platform for VMM Domains.
    choices: [ microsoft, openstack, vmware ]
'''

EXAMPLES = r''' # '''

RETURN = ''' # '''

from ansible.module_utils.network.aci.aci import ACIModule, aci_argument_spec
from ansible.module_utils.basic import AnsibleModule

VM_PROVIDER_MAPPING = dict(microsoft="uni/vmmp-Microsoft/dom-", openstack="uni/vmmp-OpenStack/dom-", vmware="uni/vmmp-VMware/dom-")


def main():
    argument_spec = aci_argument_spec
    argument_spec.update(
        aep=dict(type='str', aliases=['aep_name']),
        domain=dict(type='str', aliases=['domain_name', 'domain_profile']),
        domain_type=dict(type='str', choices=['phys', 'vmm'], aliases=['type']),
        state=dict(type='str', default='present', choices=['absent', 'present', 'query']),
        vm_provider=dict(type='str', choices=['microsoft', 'openstack', 'vmware']),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ['domain_type', 'vmm', ['vm_provider']],
            ['state', 'absent', ['aep', 'domain', 'domain_type']],
            ['state', 'present', ['aep', 'domain', 'domain_type']],
        ],
    )

    aep = module.params['aep']
    domain = module.params['domain']
    domain_type = module.params['domain_type']
    vm_provider = module.params['vm_provider']
    state = module.params['state']

    if domain_type == 'phys' and vm_provider is not None:
        module.fail_json(msg="Domain type 'phys' cannot have a 'vm_provider'")

    # Compile the full domain for URL building
    if domain_type == 'vmm':
        aep_domain = '{}{}'.format(VM_PROVIDER_MAPPING[vm_provider], domain)
    elif domain_type is not None:
        aep_domain = 'uni/phys-{}'.format(domain)
    else:
        aep_domain = None

    aci = ACIModule(module)
    aci.construct_url(
        root_class=dict(
            aci_class='infraAttEntityP',
            aci_rn='infra/attentp-{}'.format(aep),
            filter_target='eq(infraAttEntityP.name, "{}")'.format(aep),
            module_object=aep,
        ),
        subclass_1=dict(
            aci_class='infraRsDomP',
            aci_rn='rsdomP-[{}]'.format(aep_domain),
            filter_target='eq(infraRsDomP.tDn, "{}")'.format(aep_domain),
            module_object=aep_domain,
        ),
    )

    aci.get_existing()

    if state == 'present':
        # Filter out module params with null values
        aci.payload(
            aci_class='infraRsDomP',
            class_config=dict(tDn=aep_domain),
        )

        # Generate config diff which will be used as POST request body
        aci.get_diff(aci_class='infraRsDomP')

        # Submit changes if module not in check_mode and the proposed is different than existing
        aci.post_config()

    elif state == 'absent':
        aci.delete_config()

    module.exit_json(**aci.result)


if __name__ == "__main__":
    main()
