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

# CI-required python3 boilerplate
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import socket
import time

from datetime import datetime, timedelta

from ansible.plugins.action import ActionBase

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class TimedOutException(Exception):
    pass


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    DEFAULT_SHUTDOWN_TIMEOUT = 600
    DEFAULT_REBOOT_TIMEOUT = 600
    DEFAULT_CONNECT_TIMEOUT = 5
    DEFAULT_PRE_REBOOT_DELAY = 2
    DEFAULT_POST_REBOOT_DELAY = 0
    DEFAULT_TEST_COMMAND = 'whoami'
    DEFAULT_REBOOT_MESSAGE = 'Reboot initiated by Ansible.'

    platforms = dict(
        Windows = dict(
          reboot = 'shutdown /r /t %(pre_reboot_delay)d /c "%(reboot_message)s"',
        ),
        default = dict(
          reboot = 'shutdown -r now "%(reboot_message)s"',
        ),
    )

    def do_until_success_or_timeout(self, what, timeout, connect_timeout, what_desc, fail_sleep=1):
        max_end_time = datetime.utcnow() + timedelta(seconds=timeout)

        e = None
        while datetime.utcnow() < max_end_time:
            try:
                what(connect_timeout)
                if what_desc:
                    display.debug("reboot: %s success" % what_desc)
                return
            except Exception as e:
                if what_desc:
                    display.debug("reboot: %s fail (expected), retrying in %d seconds..." % (what_desc, fail_sleep))
                time.sleep(fail_sleep)

        raise TimedOutException("timed out waiting for %s: %s" % (what_desc, e))

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        shutdown_timeout = int(self._task.args.get('shutdown_timeout', self.DEFAULT_SHUTDOWN_TIMEOUT))
        reboot_timeout = int(self._task.args.get('reboot_timeout', self.DEFAULT_REBOOT_TIMEOUT))
        connect_timeout = int(self._task.args.get('connect_timeout', self.DEFAULT_CONNECT_TIMEOUT))
        pre_reboot_delay = int(self._task.args.get('pre_reboot_delay', self.DEFAULT_PRE_REBOOT_DELAY))
        post_reboot_delay = int(self._task.args.get('post_reboot_delay', self.DEFAULT_POST_REBOOT_DELAY))
        test_command = str(self._task.args.get('test_command', self.DEFAULT_TEST_COMMAND))
        msg = str(self._task.args.get('msg', self.DEFAULT_REBOOT_MESSAGE))

        if self._play_context.check_mode:
            display.vvv("reboot: skipping for check_mode")
            return dict(skipped=True)

        result = super(ActionModule, self).run(tmp, task_vars)

        host = task_vars.get('inventory_hostname')
        os_family = task_vars['hostvars'][host].get('ansible_os_family')
        if os_family in self.platforms:
            cmds = self.platforms[os_family]
        else:
            cmds = self.platforms['default']

        # Implement pre-reboot delay in seconds if reboot_cmd does not support it
        if '%(pre_reboot_delay)d' not in cmds['reboot']:
            time.sleep(pre_reboot_delay)

        # FIXME: Implement wall support if reboot_cmd does not support it
        #if '%(reboot_message)s' not in cmds['reboot']:
        #    (rc, stdout, stderr) = self._connection.exec_command(cmds['wall'] % dict(reboot_message=msg))

        # Initiate reboot
        try:
            (rc, stdout, stderr) = self._connection.exec_command(cmds['reboot'] % dict(pre_reboot_delay=pre_reboot_delay, reboot_message=msg))
            result['rc'] = rc
            result['stdout'] = stdout
            result['stderr'] = stderr
        except Exception as e:
            # give it a second to actually die
            time.sleep(5)

        if rc != 0:
            result['failed'] = True
            result['rebooted'] = False
            result['msg'] = "Shutdown command failed, error text was %s" % stderr
            return result

        def ping_module_test(connect_timeout):
            ''' Test ping module, if available '''
            display.vvv("reboot: attempting ping module test")
            # call connection reset between runs if it's there
            try:
                self._connection._reset()
            except AttributeError:
                pass

            # Use ping on powershell
            ping_module = 'ping'
            if '.ps1' in self._connection.module_implementation_preferences:
                ping_module = 'win_ping'
            ping_result = self._execute_module(module_name=ping_module, module_args=dict(), tmp=tmp, task_vars=task_vars)

            # Test module output
            if ping_result['ping'] != 'pong':
                raise Exception('ping test failed')

        def run_test_command(connect_timeout):
            display.vvv("reboot: attempting post-reboot test command '%s'" % test_command)
            # call connection reset between runs if it's there
            try:
                self._connection._reset()
            except AttributeError:
                pass

            (rc, stdout, stderr) = self._connection.exec_command(test_command)

            if rc != 0:
                raise Exception('test command failed')

        start = datetime.now()

        try:
            # If the connection has a transport_test method, use it first
            if hasattr(self._connection, 'transport_test'):
                self.do_until_success_or_timeout(self._connection.transport_test, reboot_timeout, connect_timeout,
                    what_desc="connection port up")

            # FUTURE: ensure that a reboot has actually occurred by watching for change in last boot time fact
            # FUTURE: add a stability check (system must remain up for N seconds) to deal with self-multi-reboot updates

            # Use the ping module test to determine end-to-end connectivity
            if test_command:
                self.do_until_success_or_timeout(run_test_command, reboot_timeout, connect_timeout, what_desc="post-reboot test command success")
            else:
                self.do_until_success_or_timeout(ping_module_test, reboot_timeout, connect_timeout, what_desc="ping module test success")

            result['rebooted'] = True
            result['changed'] = True

        except TimedOutException as toex:
            result['failed'] = True
            result['rebooted'] = True
            result['msg'] = toex.message

        if post_reboot_delay != 0:
            display.vvv("reboot: waiting an additional %d seconds" % post_reboot_delay)
            time.sleep(post_reboot_delay)

        elapsed = datetime.now() - start
        result['elapsed'] = elapsed.seconds

        return result
