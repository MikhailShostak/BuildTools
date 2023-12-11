import argparse
import yaml
import json
import os
import shutil
import subprocess
import glob

from pathlib import PureWindowsPath

script_folder = os.path.dirname(os.path.abspath(__file__))

def get_tools_path():
    return PureWindowsPath((os.path.normpath(os.path.join(script_folder, "..", "Tools.bat")))).as_posix()

class ProjectTools:

    def is_outdated(self, path):
        project_path = self.project_path
        target_path = os.path.join(self.target_dir, self.target + '.target')
        project_user_path = os.path.join(os.path.dirname(project_path), '.' + os.path.splitext(os.path.basename(project_path))[0] + '.user')
        last_update_path = path

        project_mtime = os.path.getmtime(project_path)
        target_mtime = os.path.getmtime(target_path)
        project_user_mtime = os.path.getmtime(project_user_path) if os.path.exists(project_user_path) else 0
        last_update_mtime = os.path.getmtime(last_update_path) if os.path.exists(last_update_path) else 0

        return last_update_mtime < project_mtime or last_update_mtime < target_mtime or (os.path.exists(project_user_path) and last_update_mtime < project_user_mtime)

    def run(self, args):
        self.project_dir = args.Project
        self.project_name = os.path.basename(self.project_dir) + ".project"
        self.project_path = os.path.join(self.project_dir, self.project_name)

        with open(self.project_path, 'r') as f:
            self.project = yaml.load(f, Loader=yaml.FullLoader)

        self.configuration = args.Configuration
        self.target = args.Target
        self.target_dir = os.path.join(self.project_dir, self.target)

        self.build_dir = os.path.join(self.project_dir, '.Build', self.target)
        self.package_dir = self.build_dir
        self.configuration_dir = os.path.join(self.build_dir, self.configuration)
        self.generator = args.Generator
        self.linkage = args.Linkage.lower()

        if args.Command == "Generate":
            print(f"Create build directory: {self.configuration_dir}")
            os.makedirs(self.package_dir, exist_ok=True)
            os.makedirs(self.configuration_dir, exist_ok=True)
            self.compile_classes()
            self.generate()
            self.make_dev_package()
            self.install_dependencies()
            self.make_environment_file()
        elif args.Command == "Build":
            last_update_path = os.path.join(self.configuration_dir, 'last_update.txt')
            if self.is_outdated(last_update_path):
                print(f"Create build directory: {self.configuration_dir}")
                os.makedirs(self.package_dir, exist_ok=True)
                os.makedirs(self.configuration_dir, exist_ok=True)
                self.generate()
                self.make_dev_package()
                self.install_dependencies()
                open(last_update_path, 'w').close()
            self.make_environment_file()
            
            self.compile_classes()
            self.copy_assets()
            self.build()
        elif args.Command == "Package":
            os.makedirs(self.package_dir, exist_ok=True)
            self.compile_classes()
            self.generate()
            self.package()
            if args.Deploy:
                self.deploy(args.Deploy)
        else:
            return False
        return True

    def read_json_with_comments(self, path):
        data = {}
        if os.path.exists(path):
            with open(path, 'r') as f:
                lines = f.readlines()
                cleaned_lines = [line for line in lines if not line.strip().startswith("//")]
                data = json.loads('\n'.join(cleaned_lines))

        return data

    def generate_vscode_tasks(self, project, path):
        data = self.read_json_with_comments(path)
        if 'version' not in data:
            data['version'] = '2.0.0'
        if 'tasks' not in data:
            data['tasks'] = []

        for target in self.targets:
            target_name = target['Name']
            target_short_name = os.path.basename(target_name)

            build_task_name = target_short_name
            build_task = None
            for c in data['tasks']:
                if c.get('label', None) == build_task_name:
                    build_task = c
                    break

            if build_task == None:
                data['tasks'].append({'label': build_task_name})
                build_task = data['tasks'][-1]

            build_task.update({
                "label": build_task_name,
                "type": "shell",
                "command": get_tools_path(),
                "args": ["Build", f"--Target={target_name}", f"--Configuration={self.configuration}", f'--Linkage={self.linkage}', f"--Generator={self.generator}"]
            })

        with open(path, 'w') as f:
            json.dump(data, f, indent=4)

    def generate_vscode_configurations(self, project, path):
        data = self.read_json_with_comments(path)
        if 'version' not in data:
            data['version'] = '0.2.0'
        if 'configurations' not in data:
            data['configurations'] = []

        for target in self.targets:
            target_name = target['Name']
            configuration_name = target_name
            if target.get('Type', 'Application') != 'Application':
                continue

            configuration = None
            for c in data['configurations']:
                if c.get('name', None) == configuration_name:
                    configuration = c
                    break

            if configuration == None:
                data['configurations'].append({'name': configuration_name})
                configuration = data['configurations'][-1]

            vscode_program_folder = '${workspaceFolder}' + f"/.Build/{target_name}/{self.configuration}"

            configuration.update({
                "type": "cppvsdbg",
                "request": "launch",
                "preLaunchTask": target_name,
                "program": f"{vscode_program_folder}/{os.path.basename(target_name)}.exe",
                "envFile": f"{vscode_program_folder}/conanrun.env",
                "cwd": vscode_program_folder,
                "symbolSearchPath": vscode_program_folder,
                "console": "internalConsole",
                "logging": {
                    "moduleLoad": False,
                    "trace": True
                },
                "internalConsoleOptions": "openOnSessionStart",
                "visualizerFile": '${workspaceFolder}' + "/my.natvis"
            })

        with open(path, 'w') as f:
            json.dump(data, f, indent=4)

    def generate_vscode_project(self, project_path):
        vscode_dir = os.path.join(os.path.dirname(project_path), '.vscode')

        self.targets = self.project.get('Targets', [])

        target_files = glob.glob(os.path.join(self.project_dir, '**/*.target'), recursive=True)
        for target_path in target_files:
            with open(target_path, 'r') as f:
                target = yaml.load(f, Loader=yaml.FullLoader)
                target['Name'] = os.path.basename(os.path.dirname(target_path))
                self.targets.append(target)
        
        for target in self.targets:
            print('Target:', target['Name'])

        if not os.path.exists(vscode_dir):
            os.makedirs(vscode_dir)
        
        self.generate_vscode_tasks(self.project, os.path.join(vscode_dir, 'tasks.json'))
        self.generate_vscode_configurations(self.project, os.path.join(vscode_dir, 'launch.json'))

    def generate(self):
        print("Generating...")

        self.generate_vscode_project(self.project_path)

        package_info_name = 'package_info.yaml'
        package_info_path = os.path.join(self.package_dir, package_info_name)
        package_info_data = {
            "Project": self.project_path,
            "Target": self.target,
        }

        with open(package_info_path, "w") as f:
            yaml.dump(package_info_data, f)

        src_conanfile = os.path.join(script_folder, 'conanfile.py')
        dst_conanfile = os.path.join(self.package_dir, 'conanfile.py')

        print(f"Copy: {src_conanfile} to {dst_conanfile}")
        shutil.copy(src_conanfile, dst_conanfile)
        
    def make_dev_package(self):
        dst_conanfile = os.path.join(self.package_dir, 'conanfile.py')
        args = ['conan', 'editable', 'add', dst_conanfile, '--name', self.target.lower(), '--version', self.project['Version'], '--user', 'dev']
        print(*args)
        subprocess.run(args, check=True)

    def install_dependencies(self):
        dst_conanfile = os.path.join(self.package_dir, 'conanfile.py')
        args = ["conan", "install", dst_conanfile, f"--settings=build_type={self.configuration}", "--build=missing"]
        if self.generator:
            args.extend(["-c", f"tools.cmake.cmaketoolchain:generator={self.generator}"])
        if self.linkage == 'static':
            args.extend(['-o', '*:shared=False'])
        elif self.linkage == 'shared':
            args.extend(['-o', '*:shared=True'])
        print(*args)
        subprocess.run(args, check=True)

    def make_environment_file(self):
        bat_files = glob.glob(os.path.join(self.package_dir, "conanrunenv-*.bat"))

        for bat_file in bat_files:
            with open(bat_file, "r") as f:
                lines = f.readlines()

            path_line = '\n'
            for line in lines:
                if line.startswith('set "PATH='):
                    path_line = line.strip()[5:-1]
                    break

            with open(os.path.join(self.configuration_dir, "conanrun.env"), "w") as f:
                f.write(path_line)

    def compile_classes(self):
        print("Compile classes...")

        args = [os.path.join(script_folder, '..', 'RunClassGenCompiler.bat'), self.target_dir]
        print(*args)
        subprocess.run(args, check=True)

    def copy_assets(self):
        print("Copying Assets...")

        asset_source_dir = os.path.join(self.target_dir, 'Assets')
        asset_dest_dir = self.configuration_dir
        asset_list_file_path = os.path.join(self.configuration_dir, '.assets.txt')

        new_asset_list = []

        # Recursively iterate over the project directory
        for subdir, _, files in os.walk(asset_source_dir):
            for file in files:
                source_file_path = os.path.join(subdir, file)
                relative_path = os.path.relpath(source_file_path, asset_source_dir)
                dest_file_path = os.path.join(asset_dest_dir, relative_path)

                # Add to the new asset list
                new_asset_list.append(dest_file_path)

                # Create directories in the destination if they don't exist
                os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)

                # If the destination file doesn't exist or is older, copy the source file
                if not os.path.exists(dest_file_path) or os.path.getmtime(source_file_path) > os.path.getmtime(dest_file_path):
                    shutil.copy2(source_file_path, dest_file_path)
                    print(f'Copy: {source_file_path} -> {dest_file_path}')

        # Load existing asset list from the file
        existing_asset_list = []
        if os.path.exists(asset_list_file_path):
            with open(asset_list_file_path, 'r') as file:
                existing_asset_list = file.read().splitlines()
        
        # Remove assets in the destination directory that don't exist in the source directory
        for asset_path in existing_asset_list:
            if asset_path not in new_asset_list and os.path.exists(asset_path):
                print(f'Remove: {asset_path}')
                os.remove(asset_path)
        
        # Update the asset list file with the new list
        with open(asset_list_file_path, 'w') as file:
            for asset_path in new_asset_list:
                file.write(asset_path + '\n')


    def build(self):

        for target in self.project.get('Targets', []):
            if target['Name'] == self.target and target.get('Type', None) == 'Interface':
                return

        import multiprocessing
        print("Building...")

        os.chdir(self.configuration_dir)
        args = ["cmake", "--build", self.configuration_dir, f'--config={self.configuration}', '--', '-j', str(multiprocessing.cpu_count())]
        print(*args)
        subprocess.run(args, check=True)

    def package(self):
        print("Packaging...")
        args = ["conan", "create", os.path.join(self.package_dir, 'conanfile.py'), '--name', self.target.lower(), '--version', self.project['Version'], f"--settings=build_type={self.configuration}", "--build=missing"]
        if self.generator:
            args.extend(["-c", f"tools.cmake.cmaketoolchain:generator={self.generator}"])
        if self.linkage == 'static':
            args.extend(['-o', '*:shared=False'])
        elif self.linkage == 'shared':
            args.extend(['-o', '*:shared=True'])
        print(*args)
        subprocess.run(args, check=True)

    def deploy(self, remote):
        print("Deploying...")
        name = self.target.lower()
        version = self.project['Version']
        args = ["conan", "upload", f'{name}/{version}', '--remote', remote]
        print(*args)
        subprocess.run(args, check=True)


def main():
    parser = argparse.ArgumentParser(description="Script to call different functions.")
    subparsers = parser.add_subparsers(dest="Command", help="Available commands")

    generate_parser = subparsers.add_parser("Generate", help="Generate")
    generate_parser.add_argument("--Project", help="Project", default=os.getcwd())
    generate_parser.add_argument("--Target", help="Target")
    generate_parser.add_argument("--Generator", help="Generator", default=None)
    generate_parser.add_argument("--Linkage", help="Static", default=str())
    generate_parser.add_argument("--Configuration", help="Target", default='Release')

    build_parser = subparsers.add_parser("Build", help="Build")
    build_parser.add_argument("--Project", help="Project", default=os.getcwd())
    build_parser.add_argument("--Target", help="Target")
    build_parser.add_argument("--Generator", help="Generator", default=None)
    build_parser.add_argument("--Linkage", help="Static", default=str())
    build_parser.add_argument("--Configuration", help="Target", default='Release')

    package_parser = subparsers.add_parser("Package", help="Package")
    package_parser.add_argument("--Project", help="Project", default=os.getcwd())
    package_parser.add_argument("--Target", help="Target")
    package_parser.add_argument("--Generator", help="Generator", default=None)
    package_parser.add_argument("--Configuration", help="Target", default='Release')
    package_parser.add_argument("--Linkage", help="Static", default=str())
    package_parser.add_argument("--Deploy", help="Deploy", default=None)

    args = parser.parse_args()
    if not ProjectTools().run(args):
        parser.print_help()

if __name__ == "__main__":
    main()
