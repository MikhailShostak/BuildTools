import argparse
import yaml
import json
import os
import shutil
import subprocess

from pathlib import PureWindowsPath

script_folder = os.path.dirname(os.path.abspath(__file__))

def get_tools_path():
    return PureWindowsPath((os.path.normpath(os.path.join(script_folder, "..", "Tools.bat")))).as_posix()

class ProjectTools:

    def run(self, args):
        self.project_dir = args.Project
        self.project_name = os.path.basename(self.project_dir) + ".project"
        self.project_path = os.path.join(self.project_dir, self.project_name)

        self.configuration = args.Configuration
        self.target = args.Target

        self.build_dir = os.path.join(self.project_dir, '.Build', self.configuration, self.target)

        if args.Command == "Generate":
            self.generator = args.Generator
            self.generate()
        elif args.Command == "Build":
            self.build()
        elif args.Command == "Package":
            self.package()
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

        for target in project['Targets']:
            target_name = target['Name']
            target_short_name = os.path.basename(target_name)

            generate_task_name = f'G: {target_short_name}'
            generate_task = None
            for c in data['tasks']:
                if c.get('label', None) == generate_task_name:
                    generate_task = c
                    break

            if generate_task == None:
                data['tasks'].append({'label': generate_task_name})
                generate_task = data['tasks'][-1]

            generate_task.update({
                "label": generate_task_name,
                "type": "shell",
                "command": get_tools_path(),
                "args": ["Generate", f"--Target={target_name}", f"--Configuration={self.configuration}", f"--Generator=Ninja"]
            })

            if target.get('Type', None) != 'Interface':
                build_task_name = f'B: {target_short_name}'
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
                    "args": ["Build", f"--Target={target_name}", f"--Configuration={self.configuration}"]
                })

        with open(path, 'w') as f:
            json.dump(data, f, indent=4)

    def generate_vscode_configurations(self, project, path):
        data = self.read_json_with_comments(path)
        if 'version' not in data:
            data['version'] = '0.2.0'
        if 'configurations' not in data:
            data['configurations'] = []

        for target in project['Targets']:
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

            configuration.update({
                "type": "cppvsdbg",
                "request": "launch",
                "preLaunchTask": f"B: {target_name}",
                "program": '${workspaceFolder}' + f"/.Build/{self.configuration}/{target_name}/{os.path.basename(target_name)}.exe",
                "envFile": '${workspaceFolder}' + f"/.Build/{self.configuration}/{target_name}/conanrun.env",
                "symbolSearchPath": '${workspaceFolder}' + f"/.Build/{self.configuration}/{target_name}",
                "externalConsole": False,
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

        with open(project_path, 'r') as f:
            project = yaml.load(f, Loader=yaml.FullLoader)

            if not os.path.exists(vscode_dir):
                os.makedirs(vscode_dir)
            
            self.generate_vscode_tasks(project, os.path.join(vscode_dir, 'tasks.json'))
            self.generate_vscode_configurations(project, os.path.join(vscode_dir, 'launch.json'))

    def generate(self):
        print("Generating...")

        self.generate_vscode_project(self.project_path)

        build_info_name = 'build_info.yaml'
        build_info_path = os.path.join(self.build_dir, build_info_name)
        build_info_data = {
            "Project": self.project_path,
            "Target": self.target,
            "Configuration": self.configuration,
        }

        print(f"Create build directory: {self.build_dir}")
        os.makedirs(self.build_dir, exist_ok=True)

        with open(build_info_path, "w") as f:
            yaml.dump(build_info_data, f)

        src_conanfile = os.path.join(script_folder, 'conanfile.py')
        dst_conanfile = os.path.join(self.build_dir, 'conanfile.py')

        print(f"Copy: {src_conanfile} to {dst_conanfile}")
        shutil.copy(src_conanfile, dst_conanfile)

        os.chdir(self.build_dir)
        args = ["conan", "install", "conanfile.py", f"--settings=build_type={self.configuration}", "--build=missing"]
        if self.generator:
            args.extend(["-c", f"tools.cmake.cmaketoolchain:generator={self.generator}"])
        print(*args)
        subprocess.run(args, check=True)

    def build(self):
        print("Building...")

        os.chdir(self.build_dir)
        args = ["cmake", "--build", self.build_dir, f'--config={self.configuration}']
        print(*args)
        subprocess.run(args, check=True)

    def package(self):
        print("Packaging...")

def main():
    parser = argparse.ArgumentParser(description="Script to call different functions.")
    subparsers = parser.add_subparsers(dest="Command", help="Available commands")

    generate_parser = subparsers.add_parser("Generate", help="Generate")
    generate_parser.add_argument("--Project", help="Project", default=os.getcwd())
    generate_parser.add_argument("--Target", help="Target")
    generate_parser.add_argument("--Generator", help="Generator", default=None)
    generate_parser.add_argument("--Configuration", help="Target", default='Release')

    build_parser = subparsers.add_parser("Build", help="Build")
    build_parser.add_argument("--Project", help="Project", default=os.getcwd())
    build_parser.add_argument("--Target", help="Target")
    build_parser.add_argument("--Configuration", help="Target", default='Release')

    package_parser = subparsers.add_parser("Package", help="Package")

    args = parser.parse_args()
    if not ProjectTools().run(args):
        parser.print_help()

if __name__ == "__main__":
    main()
