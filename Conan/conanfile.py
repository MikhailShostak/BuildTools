from conan import ConanFile, tools
from conan.tools.cmake import CMake

import os, yaml, glob, hashlib, argparse, io
from pathlib import PureWindowsPath

script_folder = os.path.dirname(os.path.abspath(__file__))

class TargetGenerator(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "CMakeToolchain", "CMakeDeps"

    project_base_dir = '.'
    project_path = None
    target_name = None
    _target = None

    options = { "shared" : [True, False] }
    default_options = { "shared": True }

    def __init__(self, arg):
        super().__init__(arg)
        
        with open(os.path.join(script_folder, 'build_info.yaml'), 'r') as f:
            build_info = yaml.load(f, Loader=yaml.FullLoader)

        self.project_path = build_info['Project']
        self.target_name = build_info['Target']

        self.project_base_dir = PureWindowsPath(os.path.normpath(os.path.dirname(self.project_path))).as_posix()

    @property
    def target(self):
        if self._target:
            return self._target

        print(f'Loading {self.target_name} target from {self.project_path}')

        self.project = None
        with open(self.project_path, 'r') as f:
            self.project = yaml.load(f, Loader=yaml.FullLoader)

            target_path = os.path.join(os.path.dirname(self.project_path), self.target_name, self.target_name + '.target')
            if os.path.exists(target_path):
                print('Loading Target:', target_path)
                with open(target_path, 'r') as target_file:
                    self._target = yaml.load(target_file, Loader=yaml.FullLoader)
                print(self._target)
                return self._target
            else:
                for target in self.project.get('Targets', []):
                    target_name = target['Name']
                    if self.target_name.endswith(target_name):
                        self._target = target
                        self.target_name = target_name
                        return self._target

        raise RuntimeError(f'Target \"{self.target_name}\" not found.')

    @property
    def project_version(self):
        return self.project.get('Version', '1.0.0')

    @property
    def target_dir(self):
        return os.path.join(self.project_base_dir, self.target_name)

    def collect_file_paths(self, folder, extension):
        paths = glob.glob(f'{self.target_dir}/{folder}/**/.*.{extension}', recursive=True) + glob.glob(f'{self.target_dir}/{folder}/**/*.{extension}', recursive=True)
        return [PureWindowsPath((os.path.normpath(path))).as_posix() for path in paths]

    def get_all_subfolder_paths(self, folder):
        return [name for name in glob.glob(f'{self.target_dir}/{folder}/**/*/', recursive=True) if os.path.isdir(name)]

    def save_file(self, path, content):
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        file_hash = hashlib.sha256(open(path, 'rb').read()).hexdigest() if os.path.isfile(path) else None

        print(f'{path}: {file_hash} -> {content_hash}')
        if file_hash != content_hash:
            tools.files.save(self, path, content)

    def configure(self):
        dependencies = self.target.get('PublicDependencies', []) + self.target.get('PrivateDependencies', [])
        print('Configure', dependencies)

        if self.target.get('StaticLinkage', False):
            self.options['*'].shared = False
        else:
            for dependency in dependencies:
                if isinstance(dependency, dict):
                    package_name = dependency['Name']
                    package_static = bool(dependency.get('Static', False))
                else:
                    package_name = dependency
                    package_static = False
                
                package_name = package_name.split('/')[0]
                print('{}={}'.format(package_name, 'static' if package_static else 'shared'))
                self.options[package_name].shared = not package_static

    def add_dependency(self, dependency, **kwargs):
        dependency_name = dependency['Name'].split('/')
        package_name = dependency_name[0]
        package_version = dependency_name[1] if len(dependency_name) > 1 else None

        if not package_version:
            package_version = self.target.get('PackageVersion', self.project_version)

        self.requires(package_name + '/' + package_version, **kwargs)


    def requirements(self):
        for dependency in self.target.get('LocalDependencies', []):
            self.add_dependency(dependency, transitive_headers=True, transitive_libs=True)

        for dependency in self.target.get('PublicDependencies', []):
            self.add_dependency(dependency, transitive_headers=True, transitive_libs=True)

        for dependency in self.target.get('PrivateDependencies', []):
            self.add_dependency(dependency, transitive_headers=False, transitive_libs=False)

        for dependency in self.target.get('PrivateDependencyOverrides', []):
            self.add_dependency(dependency, transitive_headers=False, transitive_libs=False, override=True)

    def generate(self):
        cmake_project_path = os.path.join(str(self.folders.build_folder), 'CMakeLists.txt')
        self.output.info(f'Generate {cmake_project_path}')

        cmake_find_packages = []
        cmake_link_packages = []

        target_files = glob.glob(f'{script_folder}/*Targets.cmake')

        for path in target_files:
            package = os.path.basename(path).split('Targets.cmake')[0]
            if package.startswith('module-'):
                continue
            cmake_find_packages.append(f'find_package({package} REQUIRED)')

        import re
        print(target_files)
        for path in target_files:
            with open(path) as f:
                for line in f:
                    match = re.search(r"Conan: Target declared '([^']+)'", line)
                    if match:
                        cmake_target = match.group(1)
                        cmake_link_packages.append(cmake_target)

        cmake_target_name = os.path.basename(self.target_name)
        version = self.target.get('PackageVersion', self.project_version)

        cmake_content = [
            'cmake_minimum_required(VERSION 3.5)',
            f'project({cmake_target_name} VERSION {version})',
        ]

        if cmake_find_packages:
            cmake_content.extend(cmake_find_packages)

        source_base_dir = f'Source'
        include_base_dir = f'Include'
        print("Source Base Dir:", source_base_dir)
        print("Include Base Dir:", include_base_dir)

        source_file_paths = []
        for e in ['cpp']:
            source_file_paths.extend(self.collect_file_paths(source_base_dir, e) + self.collect_file_paths(include_base_dir, e))

        private_include_file_paths = []
        for e in ['hpp', 'h']:
            private_include_file_paths.extend(self.collect_file_paths(source_base_dir, e))
        private_inline_include_file_paths = []
        for e in ['inl']:
            private_inline_include_file_paths.extend(self.collect_file_paths(source_base_dir, e))

        include_file_paths = []
        for e in ['hpp', 'h']:
            include_file_paths.extend(self.collect_file_paths(include_base_dir, e))
        inline_include_file_paths = []
        for e in ['inl']:
            inline_include_file_paths.extend(self.collect_file_paths(include_base_dir, e))

        precompile_local_haders = self.target.get('PrecompileLocalHeaders', False)

        package_header_file_name = f'{cmake_target_name}.hpp'
        package_header_file_path = os.path.join(script_folder, package_header_file_name)

        precompiled_header_file_name = f'{cmake_target_name}.pch.hpp'
        precompiled_header_file_path = os.path.join(script_folder, package_header_file_name)

        def write_include(stream, path, local=True):
            relpath = os.path.relpath(path, start=f'{self.target_dir}/{include_base_dir}') if local else path
            relpath = PureWindowsPath((os.path.normpath(relpath))).as_posix()
            if local:
                stream.write(f'#include "{relpath}"\n')
            else:
                stream.write(f'#include <{relpath}>\n')

        def write_includes(stream, paths, local=True):
            for path in paths:
                write_include(stream, path, local)
            stream.write('\n')

        stream = io.StringIO()
        with open(package_header_file_name, 'w') as f:
            stream.write('#pragma once\n\n')
            for key, value in self.target.get('GlobalDefines', {}).items():
                stream.write(f"#define {key} {value}\n")
            for key, value in self.target.get('PublicDefines', {}).items():
                stream.write(f"#define {key} {value}\n")
            write_includes(stream, self.target.get('GlobalHeaders', []), False)
            write_includes(stream, self.target.get('PublicIncludes', []), False)
            if precompile_local_haders:
                write_includes(stream, include_file_paths)
                write_includes(stream, inline_include_file_paths)
        self.save_file(package_header_file_name, stream.getvalue())

        stream = io.StringIO()
        with open(precompiled_header_file_name, 'w') as f:
            stream.write('#pragma once\n\n')
            for key, value in self.target.get('PrivateDefines', {}).items():
                stream.write(f"#define {key} {value}\n")
            write_includes(stream, self.target.get('PrivateIncludes', []), False)
            write_include(stream, package_header_file_name, False)
            if precompile_local_haders:
                write_includes(stream, private_include_file_paths)
                write_includes(stream, private_inline_include_file_paths)
        self.save_file(precompiled_header_file_name, stream.getvalue())

        cmake_sources = ' '.join(source_file_paths)
        target_type = self.target.get('Type', 'Application')
        interface = False
        if target_type == 'Application':
            cmake_content.append(f'add_executable({cmake_target_name} {cmake_sources})')
        elif target_type == 'Library' or target_type == 'SharedLibrary' or target_type == 'StaticLibrary' or target_type == 'Plugin':
            cmake_content.append(f'add_library({cmake_target_name} {cmake_sources})')
        elif target_type == 'Interface':
            interface = True
            cmake_content.append(f'add_library({cmake_target_name} INTERFACE)')

        public_keyword = 'INTERFACE' if interface else 'PUBLIC'

        if not interface:
            cmake_content.append(f'target_compile_definitions({cmake_target_name} PRIVATE -D_WIN32_WINNT=0x0601)')
            cmake_content.append(f'target_precompile_headers({cmake_target_name} PRIVATE {precompiled_header_file_name})')

        if cmake_link_packages:
            packages = ' '.join(cmake_link_packages)
            access_keyword = public_keyword
            cmake_content.append(f'target_link_libraries({cmake_target_name} {access_keyword} {packages})')

        include_dir = os.path.relpath(os.path.join(self.target_dir, "Include"), start=script_folder)
        include_dir = PureWindowsPath((os.path.normpath(include_dir))).as_posix()
        cmake_content.append(f'target_include_directories({cmake_target_name} {public_keyword} . {include_dir})')

        if not interface:
            source_dir = os.path.relpath(os.path.join(self.target_dir, "Source"), start=script_folder)
            source_dir = PureWindowsPath((os.path.normpath(source_dir))).as_posix()
            cmake_content.append(f'target_include_directories({cmake_target_name} PRIVATE {source_dir})')

        cmake_content.append(f'set_target_properties({cmake_target_name} PROPERTIES\n\tCXX_STANDARD 17\n\tCXX_STANDARD_REQUIRED YES\n\tCXX_EXTENSIONS NO\n)')
        cmake_content.append('set(CMAKE_VERBOSE_MAKEFILE ON)')

        cmake_content = '\n'.join(cmake_content)

        print(cmake_content)

        self.save_file(cmake_project_path, cmake_content)

        cmake = CMake(self)
        cmake.configure(build_script_folder=self.folders.build_folder)

        bat_files = glob.glob("conanrunenv-*.bat")

        for bat_file in bat_files:
            with open(bat_file, "r") as f:
                lines = f.readlines()

            path_line = '\n'
            for line in lines:
                if line.startswith('set "PATH='):
                    path_line = line.strip()[5:-2]
                    break

            with open("conanrun.env", "w") as f:
                f.write(path_line)

    def build(self):
        cmake = CMake(self)
        cmake.configure(build_script_folder=self.folders.build_folder)
        cmake.build()

    def package_info(self):
        self.cpp_info.includedirs = ['.', os.path.relpath(os.path.join(self.target_dir, 'Include'), start=script_folder)]

        target_type = self.target['Type']
        if target_type == 'Library' or target_type == 'StaticLibrary' or target_type == 'SharedLibrary' or target_type == 'Plugin':
            self.cpp_info.bindirs = ['.']
            self.cpp_info.libdirs = ['.']
            self.cpp_info.libs = [os.path.basename(self.target_name)]

        #libs = tools.files.collect_libs(self)
        #with open('W:/collected.txt', 'w') as f:
        #    f.write(script_folder + '\n')
        #    f.write(os.getcwd() + '\n')
        #    f.write(str(self.cpp_info.libdirs) + '\n')
        #    f.write(str(self.cpp_info.libs) + '\n')
        #    f.write(str(libs) + '\n')

