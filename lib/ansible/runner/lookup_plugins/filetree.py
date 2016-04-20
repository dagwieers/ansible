# (c) 2016 Dag Wieers <dag@wieers.com>
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

import os
import pwd
import grp
import stat

from ansible.utils import (listify_lookup_plugin_terms, path_dwim, warning)

HAVE_SELINUX=False
try:
    import selinux
    HAVE_SELINUX=True
except ImportError:
    pass

def _to_filesystem_str(path):
    '''Returns filesystem path as a str, if it wasn't already.

    Used in selinux interactions because it cannot accept unicode
    instances, and specifying complex args in a playbook leaves
    you with unicode instances.  This method currently assumes
    that your filesystem encoding is UTF-8.

    '''
    if isinstance(path, unicode):
        path = path.encode("utf-8")
    return path

# If selinux fails to find a default, return an array of None
def selinux_context(path):
    context = [None, None, None, None]
    if HAVE_SELINUX and selinux.is_selinux_enabled():
        try:
            ret = selinux.lgetfilecon_raw(_to_filesystem_str(path))
        except OSError:
            return context
        if ret[0] != -1:
            # Limit split to 4 because the selevel, the last in the list,
            # may contain ':' characters
            context = ret[1].split(':', 3)
    return context

def file_props(root, path):
    ''' Returns dictionary with file properties, or return None on failure '''
    abspath = os.path.join(root, path)

    try:
        st = os.lstat(abspath)
    except OSError as e:
        warning('filetree: Error using stat() on path %s (%s)' % (abspath, e))
        return None

    ret = dict(root=root, path=path)

    if stat.S_ISLNK(st.st_mode):
        ret['state'] = 'link'
        ret['src'] = os.readlink(abspath)
    elif stat.S_ISDIR(st.st_mode):
        ret['state'] = 'directory'
    elif stat.S_ISREG(st.st_mode):
        ret['state'] = 'file'
        ret['src'] = abspath
    else:
        warning('filetree: Error file type of %s is not supported' % abspath)
        return None

    ret['uid'] = st.st_uid
    ret['gid'] = st.st_gid
    try:
        ret['owner'] = pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        ret['owner'] = st.st_uid
    try:
        ret['group'] = grp.getgrgid(st.st_gid).gr_name
    except KeyError:
        ret['group'] = st.st_gid
    ret['mode'] = str(oct(stat.S_IMODE(st.st_mode)))
    ret['size'] = st.st_size
    ret['mtime'] = st.st_mtime
    ret['ctime'] = st.st_ctime

    if HAVE_SELINUX and selinux.is_selinux_enabled() == 1:
        context = selinux_context(abspath)
        ret['seuser'] = context[0]
        ret['serole'] = context[1]
        ret['setype'] = context[2]
        ret['selevel'] = context[3]

    return ret


class LookupModule(object):

    def __init__(self, basedir=None, runner=None, **kwargs):
        self.runner = runner
        self.basedir = self.runner.basedir

    def run(self, terms, inject=None, **kwargs):

        terms = listify_lookup_plugin_terms(terms, self.basedir, inject)

        ret = []
        for term in terms:
            term_file = os.path.basename(term)
            dwimmed_path = path_dwim(self.basedir, os.path.dirname(term))
            path = os.path.join(dwimmed_path, term_file)
            for root, dirs, files in os.walk(path, topdown=True):
                for entry in dirs + files:
                    relpath = os.path.relpath(os.path.join(root, entry), path)

                    # Skip if relpath was already processed (from another root)
                    if relpath not in [ entry['path'] for entry in ret ]:
                        props = file_props(path, relpath)
                        if props is not None:
                            ret.append(props)

        return ret