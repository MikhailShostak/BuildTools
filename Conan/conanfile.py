from conan import ConanFile, tools
from conan.tools.files import copy
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
        
        with open(os.path.join(script_folder, 'package_info.yaml'), 'r') as f:
            package_info = yaml.load(f, Loader=yaml.FullLoader)

        self.project_relpath = package_info['Project']
        self.project_path = os.path.join(script_folder, package_info['Project'])
        self.target_name = package_info['Target']

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
    def project_source_dir(self):
        return PureWindowsPath(os.path.join(self.source_folder, os.path.dirname(self.project_relpath))).as_posix()

    @property
    def target_dir(self):
        return PureWindowsPath(os.path.join(self.project_source_dir, self.target_name)).as_posix()

    @property
    def cmake_build_folder(self):
        return os.path.join(self.build_folder)

    def collect_file_paths(self, folder, extension):
        paths = glob.glob(f'{self.target_dir}/{folder}/**/.*.{extension}', recursive=True) + glob.glob(f'{self.target_dir}/{folder}/**/*.{extension}', recursive=True)
        return [PureWindowsPath((os.path.normpath(path))).as_posix() for path in paths]

    def get_all_subfolder_paths(self, folder):
        return [name for name in glob.glob(f'{self.target_dir}/{folder}/**/*/', recursive=True) if os.path.isdir(name)]

    def save_file(self, path, content):
        path = os.path.join(self.cmake_build_folder, path)
        print('Write:', path)
        
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        file_hash = hashlib.sha256(tools.files.load(self, path).encode()).hexdigest() if os.path.isfile(path) else None

        print(f'{path}: {file_hash} -> {content_hash}')
        if file_hash != content_hash:
            tools.files.save(self, path, content)

    def export(self):
        package_info_name = 'package_info.yaml'
        package_info_path = os.path.join(self.export_folder, package_info_name)
        package_info_data = {
            "Project": os.path.basename(self.project_path),
            "Target": self.target_name,
        }

        with open(package_info_path, "w") as f:
            yaml.dump(package_info_data, f)

        copy(self, '*.Project', self.project_base_dir, self.export_folder)
        copy(self, os.path.join(self.target_name, '*.Target'), self.project_base_dir, self.export_folder)

    def export_sources(self):
        #copy(self, 'CMakeLists.txt', self.recipe_folder, self.export_sources_folder)
        #copy(self, '*.hpp', self.recipe_folder, self.export_sources_folder)
        copy(self, '*.Project', self.project_base_dir, self.export_sources_folder)
        copy(self, f'{self.target_name}/**', self.project_base_dir, self.export_sources_folder)
    
    def configure(self):
        print('**** CONFIGURE')
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
        
        self.requires(package_name.lower() + '/' + package_version, override=bool(dependency.get('Override', False)), **kwargs)


    def requirements(self):
        print('**** REQUIREMENTS')
        for dependency in self.target.get('LocalDependencies', []):
            self.add_dependency(dependency, transitive_headers=True, transitive_libs=True)

        for dependency in self.target.get('PublicDependencies', []):
            self.add_dependency(dependency, transitive_headers=True, transitive_libs=True)

        for dependency in self.target.get('PrivateDependencies', []):
            self.add_dependency(dependency, transitive_headers=False, transitive_libs=False)

        for dependency in self.target.get('PrivateDependencyOverrides', []):
            self.add_dependency(dependency, transitive_headers=False, transitive_libs=False)

    def layout(self):
        self.folders.build = str(self.settings.build_type)
    
    def make_source_path(self, path):
        return '${PROJECT_SOURCE_ROOT_FOLDER}/' + PureWindowsPath(os.path.relpath(path, start=self.project_source_dir)).as_posix()

    def make_source_paths(self, paths):
        return [self.make_source_path(path) for path in paths]

    def generate(self):
        print('**** GENERATE')
        print('\tCWD: ', os.getcwd())
        print('\tPROJECT DIR: ', self.project_base_dir, self.project_source_dir)
        print('\tSOURCE DIR: ', self.source_folder)
        print('\tBUILD DIR: ', self.build_folder, self.cmake_build_folder)
        print('\tTARGET DIR: ', self.target_dir)

        cmake_project_path = os.path.join(self.cmake_build_folder, 'CMakeLists.txt')
        self.output.info(f'Generate {cmake_project_path}')

        cmake_find_packages = []
        cmake_link_packages = []

        target_files = glob.glob(f'{self.source_folder}/*Targets.cmake')

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

        source_base_dir = f'Source'
        include_base_dir = f'Include'
        print("Source Base Dir:", source_base_dir)
        print("Include Base Dir:", include_base_dir)

        source_file_paths = []
        for e in ['cpp']:
            source_file_paths.extend(self.collect_file_paths(source_base_dir, e) + self.collect_file_paths(include_base_dir, e))
        print('**** SOURCES: ', source_file_paths)
        public_module_source_file_paths = []
        private_module_source_file_paths = []
        for e in ['ixx']:
            public_module_source_file_paths.extend(self.collect_file_paths(include_base_dir, e))
            private_module_source_file_paths.extend(self.collect_file_paths(source_base_dir, e))

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
        precompile_public_haders = self.target.get('PrecompilePublicHeaders', precompile_local_haders)
        precompile_private_haders = self.target.get('PrecompilePrivateHeaders', precompile_local_haders)

        package_header_file_name = f'{cmake_target_name}.hpp'

        precompiled_header_file_name = f'{cmake_target_name}.pch.hpp'

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
        stream.write('#pragma once\n\n')
        for key, value in self.target.get('PublicDefines', {}).items():
            stream.write(f"#define {key} {value}\n")
        write_includes(stream, self.target.get('PublicIncludes', []), False)
        
        write_includes(stream, include_file_paths)
        write_includes(stream, inline_include_file_paths)
        self.save_file(package_header_file_name, stream.getvalue())

        stream = io.StringIO()
        stream.write('#pragma once\n\n')
        for key, value in self.target.get('PrivateDefines', {}).items():
            stream.write(f"#define {key} {value}\n")
        if not precompile_public_haders:
            for key, value in self.target.get('PublicDefines', {}).items():
                stream.write(f"#define {key} {value}\n")
        
        write_includes(stream, self.target.get('PrivateIncludes', []), False)

        if precompile_public_haders:
            write_include(stream, package_header_file_name, False)
        else:
            write_includes(stream, self.target.get('PublicIncludes', []), False)
        
        if precompile_private_haders:
            write_includes(stream, private_include_file_paths)
            write_includes(stream, private_inline_include_file_paths)
        self.save_file(precompiled_header_file_name, stream.getvalue())

        cmake_content = [
            'cmake_minimum_required(VERSION 3.26)',
            f'project({cmake_target_name} VERSION {version})',
            'set(PROJECT_SOURCE_ROOT_FOLDER "." CACHE STRING "Project Root")',
            'message(PROJECT_SOURCE_ROOT_FOLDER="${PROJECT_SOURCE_ROOT_FOLDER}")',
        ]

        if private_module_source_file_paths or public_module_source_file_paths:
            cmake_content.extend([
                'if(${CMAKE_VERSION} VERSION_LESS "3.27.0")',
                '    set(CMAKE_EXPERIMENTAL_CXX_MODULE_CMAKE_API "2182bf5c-ef0d-489a-91da-49dbc3090d2a")',
                'else()',
                '    set(CMAKE_EXPERIMENTAL_CXX_MODULE_CMAKE_API "aa1f7df0-828a-4fcd-9afc-2dc80491aca7")',
                'endif()',
                'set(CMAKE_EXPERIMENTAL_CXX_MODULE_DYNDEP 1)',
                'set(CMAKE_CXX_EXTENSIONS OFF)',
            ])

        if cmake_find_packages:
            cmake_content.extend(cmake_find_packages)

        cmake_sources = '\n\t'.join(self.make_source_paths(source_file_paths))
        target_type = self.target.get('Type', 'Application')
        interface = False
        if target_type == 'Application':
            cmake_content.append(f'add_executable({cmake_target_name}\n\t{cmake_sources}\n)')

            def write_modules(access, paths):
                if not paths:
                    return

                cmake_module_dirs = []
                for path in paths:
                    dir = os.path.dirname(path)
                    if dir not in cmake_module_dirs:
                        cmake_module_dirs.append(dir)
                cmake_module_dirs = 'BASE_DIRS ' + ' '.join(cmake_module_dirs) if len(cmake_module_dirs) else ''

                cmake_module_sources = 'FILES ' + ' '.join(paths)
                cmake_content.append(f'target_sources({cmake_target_name} {access} FILE_SET cxx_modules TYPE CXX_MODULES {cmake_module_dirs} {cmake_module_sources})')

            write_modules('PUBLIC', public_module_source_file_paths)
            write_modules('PRIVATE', private_module_source_file_paths)
        elif target_type == 'Library' or target_type == 'Plugin':
            cmake_content.append(f'add_library({cmake_target_name} {cmake_sources})')
        elif target_type == 'Interface':
            interface = True
            cmake_content.append(f'add_library({cmake_target_name} INTERFACE)')

        public_keyword = 'INTERFACE' if interface else 'PUBLIC'

        if not interface:
            cmake_content.append(f'target_compile_definitions({cmake_target_name} PRIVATE -D_WIN32_WINNT=0x0601)')
            if not public_module_source_file_paths and not private_module_source_file_paths:
                cmake_content.append(f'target_precompile_headers({cmake_target_name} PRIVATE {precompiled_header_file_name})')

        if cmake_link_packages:
            packages = '\n\t'.join(cmake_link_packages)
            access_keyword = public_keyword
            cmake_content.append(f'target_link_libraries({cmake_target_name}\n{access_keyword}\n\t{packages}\n)')

        include_dir = os.path.join('${PROJECT_SOURCE_ROOT_FOLDER}', self.target_name, "Include")
        include_dir = PureWindowsPath((os.path.normpath(include_dir))).as_posix()
        cmake_content.append(f'target_include_directories({cmake_target_name}\n{public_keyword}\n\t.\n\t"{include_dir}"\n)')

        if not interface:
            source_dir = os.path.join('${PROJECT_SOURCE_ROOT_FOLDER}', self.target_name, "Source")
            source_dir = PureWindowsPath((os.path.normpath(source_dir))).as_posix()
            cmake_content.append(f'target_include_directories({cmake_target_name} PRIVATE "{source_dir}")')
            cmake_content.append(f'if (MSVC)\n\ttarget_compile_options({cmake_target_name} PRIVATE /bigobj)\nendif ()\n')

        cmake_content.append('message(PROJECT_SOURCE_ROOT_FOLDER="${PROJECT_SOURCE_ROOT_FOLDER}")')
        public_headers = self.make_source_paths(include_file_paths)
        public_headers = ';'.join(public_headers)
        cmake_content.append(f'set_target_properties({cmake_target_name} PROPERTIES\n\tPUBLIC_HEADER "{public_headers}"\n)')
        cmake_content.append(f'set_target_properties({cmake_target_name} PROPERTIES\n\tCXX_STANDARD 20\n\tCXX_STANDARD_REQUIRED YES\n\tCXX_EXTENSIONS NO\n)')
        cmake_content.append('set(CMAKE_VERBOSE_MAKEFILE ON)')
        cmake_content.append(f'install(TARGETS {cmake_target_name})')

        cmake_content = '\n'.join(cmake_content)

        print(cmake_content)

        self.save_file(cmake_project_path, cmake_content)

        cmake = CMake(self)
        cmake.configure(variables={ 'PROJECT_SOURCE_ROOT_FOLDER': self.project_source_dir }, build_script_folder=self.cmake_build_folder)

    def build(self):
        print('**** Build:', os.getcwd(), self.project_base_dir, self.project_source_dir)
        cmake = CMake(self)
        cmake.configure(variables={ 'PROJECT_SOURCE_ROOT_FOLDER': self.project_source_dir }, build_script_folder=self.cmake_build_folder)
        cmake.build()

    def get_package_subfolder(self, subfolder):
        return os.path.join(self.package_folder, self.target_name, subfolder)
    
    def get_binaries_folder(self):
        p = self.get_package_subfolder('Binaries')
        return p if os.path.exists(p) else os.path.join(self.package_folder, str(self.settings.build_type))

    def package(self):
        print(f'**** PACKAGE: {self.source_folder} -> {self.package_folder}')
        copy(self, f'**', os.path.join(self.source_folder, self.target_name, 'Assets'), self.get_binaries_folder())
        copy(self, f'{self.target_name}/Include/**.h', self.source_folder, self.package_folder)
        copy(self, f'{self.target_name}/Include/**.hpp', self.source_folder, self.package_folder)
        copy(self, f'{self.target_name}/Include/**.inl', self.source_folder, self.package_folder)
        
        copy(self, self.target_name + '.*', os.path.join(self.source_folder, str(self.settings.build_type)), self.get_binaries_folder())

    def package_info(self):
        print('**** PACKAGE INFO:', self.package_folder)
        includes = [self.get_binaries_folder()]
        if os.path.exists(os.path.join(self.package_folder, self.target_name)):
            includes.append(f'{self.target_name}/Include')
        else:
            includes.append(f'{self.project_base_dir}/{self.target_name}/Include')
        self.cpp_info.includedirs = includes

        binaries = [self.get_binaries_folder()]
        self.cpp_info.bindirs = binaries

        target_type = self.target['Type']
        if target_type == 'Library' or target_type == 'Plugin':
            self.cpp_info.libdirs = binaries
            self.cpp_info.libs = [os.path.basename(self.target_name)]
