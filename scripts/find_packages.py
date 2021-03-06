#!/usr/bin/env python3

import os.path
import sys

scripts_path = os.path.dirname(os.path.realpath(__file__))
bb_lib_path = os.path.abspath(scripts_path + '/../../poky/bitbake/lib')
sys.path = sys.path + [bb_lib_path]

import bb.fetch2
import bb.tinfoil


def print_deps(tinfoil, abcd_file, rn):
    try:
        info = tinfoil.get_recipe_info(rn)
    except Exception:
        print('Failed to get recipe info for: %s' % rn)
        return []
    if not info:
        print('No recipe info found for: %s' % rn)
        return []
    append_files = tinfoil.get_file_appends(info.fn)
    appends = True
    data = tinfoil.parse_recipe_file(info.fn, appends, append_files)
    src_uri = data.getVar('SRC_URI').split()
    lic = data.getVar('LICENSE')
    summary = data.getVar('SUMMARY')
    description = data.getVar('DESCRIPTION')
    homepage = data.getVar('HOMEPAGE')
    srcrev = data.getVar('SRCREV')
    branch = data.getVar('BRANCH')
    depends = data.getVar('DEPENDS').split()

    abcd_file.write('- id:\n')
    abcd_file.write('    package_manager: "Yocto"\n')
    abcd_file.write('    name: "%s"\n' % info.pn)
    abcd_file.write('    version: "%s"\n' % info.pv)
    abcd_file.write('  declared_lics:\n')
    abcd_file.write('  - "%s"\n' % lic)
    if summary:
        abcd_file.write('  description: "%s"\n' % summary)
    else:
        abcd_file.write('  description: "%s"\n' % description)
    abcd_file.write('  homepage_url: "%s"\n' % homepage)
    abcd_file.write('  source_artifact:\n')
    repos = []
    for src in src_uri:
        # Strip options.
        # TODO: ignore files with apply=false?
        src = src.split(';', maxsplit=1)[0]
        src_type = src.split('://', maxsplit=1)[0]
        if src_type == 'file':
            # TODO: Get full path of patches and other files within the source
            # repo, not just the filesystem?
            fetch = bb.fetch2.Fetch([], data)
            local = fetch.localpath(src)
            abcd_file.write('  - "%s"\n' % local)
        else:
            abcd_file.write('  - "%s"\n' % src)
            if src_type != 'http' and src_type != 'https' and src_type != 'ftp' and src_type != 'ssh':
                repos.append(src)
    if len(repos) > 1:
        print('Multiple repos not fully supported yet. Pacakge: %s' % info.pn)
    for repo in repos:
        vcs_type, url = repo.split('://', maxsplit=1)
        abcd_file.write('  vcs:\n')
        if vcs_type == 'gitsm':
            vcs_type = 'git'
        abcd_file.write('    type: "%s"\n' % vcs_type)
        abcd_file.write('    url: "%s"\n' % url)
        # TODO: Actually support multiple repos here:
        abcd_file.write('    revision: "%s"\n' % srcrev)
        abcd_file.write('    branch: "%s"\n' % branch)

    abcd_file.write('  dependencies:\n')
    for dep in depends:
        abcd_file.write('  - "%s"\n' % dep)
        # TODO: search for transitive dependencies here? Each dependency will
        # get checked for its own dependencies sooner or later.

    return depends


def main():
    abcd_manifest = 'manifest.abcd'
    with open(abcd_manifest, "w") as abcd_file, bb.tinfoil.Tinfoil() as tinfoil:
        tinfoil.prepare()
        # These are the packages that bitbake assumes are provided by the host
        # system. They do not have recipes, so searching tinfoil for them will
        # not work. Anyway, by nature they are not included in code we release,
        # only used by it.
        assume_provided = tinfoil.config_data.getVar('ASSUME_PROVIDED').split()
        abcd_file.write('packages:\n')

        # Does NOT include garage-sign, anything used only for testing (i.e.
        # strace and gtest), any of the git submodules, all of which are also
        # only used for testing (tuf-test-vectors, isotp-c, ostreesysroot,
        # and HdrHistogram_c), or any other third party modules included
        # directly into the source tree (jsoncpp, open62541, picojson)
        recipes_to_check = ['aktualizr',
                            'aktualizr-native',
                            'aktualizr-auto-prov',
                            'aktualizr-implicit-prov',
                            'aktualizr-ca-implicit-prov',
                            'aktualizr-hsm-prov',
                            'aktualizr-disable-send-ip',
                            'aktualizr-example-interface',
                            'aktualizr-log-debug',
                            'libp11', # BUILD_P11 (HSM) only
                            'dpkg', # BUILD_DEB only
                            'systemd'] # BUILD_SYSTEMD only

        # Iterate through the list of recipes to check. Append any dependencies
        # found that aren't already in the list. As long as we only add to the
        # list, it should be safe.
        for recipe in recipes_to_check:
            depends = print_deps(tinfoil, abcd_file, recipe)
            for dep in depends:
                if dep not in recipes_to_check and dep not in assume_provided:
                    recipes_to_check.append(dep)


if __name__ == "__main__":
    main()
