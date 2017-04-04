#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2017, Dag Wieers <dag@wieers.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.


ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['stableinterface'],
                    'supported_by': 'core'}


DOCUMENTATION = r'''
---
module: reboot
short_description: Reboot a Linux/Unix system
description:
- Reboot a Linux/Unix machine, wait for it to go down, come back up, and respond to commands.
version_added: "2.4"
options:
  pre_reboot_delay:
    description:
    - Seconds for shutdown to wait before requesting reboot
    default: 2
  post_reboot_delay:
    description:
    - Seconds to wait after the reboot was successful and the connection was re-established
    - This is useful if you want wait for something to settle despite your connection already working
    default: 0
  shutdown_timeout:
    description:
    - Maximum seconds to wait for shutdown to occur
    - Increase this timeout for very slow hardware, large update applications, etc
    default: 600
  reboot_timeout:
    description:
    - Maximum seconds to wait for machine to re-appear on the network and respond to a test command
    - This timeout is evaluated separately for both network appearance and test command success (so maximum clock time is actually twice this value)
    default: 600
  connect_timeout:
    description:
    - Maximum seconds to wait for a single successful transport connection before trying again
    default: 5
  test_command:
    description:
    - Command to expect success for to determine the machine is ready for management
    - By default C(reboot) will try the M(ping) module for determining end-to-end connectivity
  msg:
    description:
    - Message to display to users
    default: Reboot initiated by Ansible
notes:
- If a shutdown was already scheduled on the system, C(reboot) will abort the scheduled shutdown and enforce its own shutdown.
author:
    - Dag Wieers (@dagwieers)
'''

EXAMPLES = r'''
# Unconditionally reboot the machine with all defaults
- reboot:

# Apply updates and reboot if necessary
- yum:
    name: '*'
    state: latest
  register: update_result
- reboot:
  when: update_result|changed

# Reboot a slow machine that might have lots of updates to apply
- reboot:
    shutdown_timeout: 300
    reboot_timeout: 600
'''

RETURN = r'''
rebooted:
    description: true if the machine was rebooted
    returned: always
    type: boolean
    sample: true

elapsed:
  description: The number of seconds that elapsed waiting for the system to be rebooted.
  returned: always
  type: integer
  sample: 23
'''
