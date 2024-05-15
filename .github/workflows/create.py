import os
import requests
import shutil
import json

def fetch_module_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Failed to fetch data from {url}: {e}")
        return None

def create_provider_tf(directory, provider):
    with open(os.path.join(directory, 'provider.tf'), 'w') as f:
        f.write('terraform {\n')
        f.write('  required_version = ">= 1.6.0, < 2.0.0"\n')
        f.write('  required_providers {\n')
        if provider == 'google':
            f.write('    google = {\n')
            f.write('      source  = "hashicorp/google"\n')
            f.write('      version = "~> 5.21.0"\n')
            f.write('    }\n')
        elif provider == 'aws':
            f.write('    aws = {\n')
            f.write('      source  = "hashicorp/aws"\n')
            f.write('      version = ">= 5.33"\n')
            f.write('    }\n')
        f.write('  }\n')
        f.write('}\n')

def create_repo(namespace, tf_module_name, module_name, provider, version, submodules=None):
        # Fetch the root module details
        root_url = f"https://registry.terraform.io/v1/modules/{namespace}/{tf_module_name}/{provider}/{version}"
        data = fetch_module_data(root_url)
        
        if not data:
            return None

        # Parse root module inputs and outputs
        root_inputs = {}
        root_outputs = {}

        if 'root' in data:
            root_module_data = data['root']
            for input in root_module_data['inputs']:
                root_inputs[input['name']] = {"description": input['description'], "default": input.get('default'), "type": input['type']}
            for output in root_module_data['outputs']:
                root_outputs[output['name']] = {"description": output['description']}

        # Create the module folders and files for the root module
        root_dir = f'examples/{module_name}'
        os.makedirs(root_dir, exist_ok=True)

        # Write root module main.tf
        with open(f'{root_dir}/main.tf', 'w') as f:
            f.write(f'module "{module_name}" {{\n')
            f.write('  # Module source and version\n')
            f.write(f'  source = "{namespace}/{tf_module_name}/{provider}"\n')
            f.write(f'  version = "{version}"\n')
            f.write('\n')
            f.write('  # Module inputs\n')

            # Write root module inputs
            for name, details in root_inputs.items():
                f.write(f'  {name.ljust(50)} = var.{name}\n')

            f.write('\n')
            f.write('  # MCD Overrides\n')
            f.write('}\n')

        # Write root module variables.tf
        with open(f'{root_dir}/variables.tf', 'w') as f:
            for name, details in root_inputs.items():
                f.write(f'variable "{name}" {{\n')
                f.write(f'  description = "{details["description"]}"\n')
                f.write(f'  type = {details["type"]}\n')
                if "default" in details:
                    f.write(f'  default = {details["default"]}\n')
                f.write('}\n\n')

        # Write root module output.tf
        with open(f'{root_dir}/output.tf', 'w') as f:
            for name, details in root_outputs.items():
                f.write(f'output "{name}" {{\n')
                f.write(f'  description = "{details["description"]}"\n')
                f.write(f'  value = module.{module_name}.{name}\n')
                f.write('}\n\n')

        # Write root module provider.tf
        create_provider_tf(root_dir, provider)

        # Include submodules if specified
        submodules_data = {}
        if submodules and 'submodules' in data:
            for submodule in submodules:
                submodule_data = next((sm for sm in data['submodules'] if sm['name'] == submodule), None)

                if submodule_data:
                    submodule_inputs = {input['name']: {"description": input['description'], "default": input.get('default'), "type": input['type']} for input in submodule_data['inputs']}
                    submodule_outputs = {output['name']: {"description": output['description']} for output in submodule_data['outputs']}
                    submodules_data[submodule] = {'inputs': submodule_inputs, 'outputs': submodule_outputs}

                    submodule_dir = f'examples/{submodule}'
                    os.makedirs(submodule_dir, exist_ok=True)

                    # Write submodule main.tf
                    with open(f'{submodule_dir}/main.tf', 'w') as sub_f:
                        sub_f.write(f'module "{submodule}" {{\n')
                        sub_f.write('  # Submodule source and version\n')
                        sub_f.write(f'  source = "{namespace}/{tf_module_name}/{provider}//modules/{submodule}"\n')
                        sub_f.write(f'  version = "{version}"\n')
                        sub_f.write('\n')
                        sub_f.write('  # Submodule inputs\n')

                        # Write submodule inputs
                        for name, details in submodule_inputs.items():
                            sub_f.write(f'  {name.ljust(50)} = var.{name}\n')

                        sub_f.write('}\n')

                    # Write submodule variables.tf
                    with open(f'{submodule_dir}/variables.tf', 'w') as sub_f:
                        for name, details in submodule_inputs.items():
                            sub_f.write(f'variable "{name}" {{\n')
                            sub_f.write(f'  description = "{details["description"]}"\n')
                            sub_f.write(f'  type = {details["type"]}\n')
                            if "default" in details:
                                sub_f.write(f'  default = {details["default"]}\n')
                            sub_f.write('}\n\n')

                    # Write submodule output.tf
                    with open(f'{submodule_dir}/output.tf', 'w') as sub_f:
                        for name, details in submodule_outputs.items():
                            sub_f.write(f'output "{name}" {{\n')
                            sub_f.write(f'  description = "{details["description"]}"\n')
                            sub_f.write(f'  value = module.{submodule}.{name}\n')
                            sub_f.write('}\n\n')

                    # Write submodule provider.tf
                    create_provider_tf(submodule_dir, provider)
                else:
                    print(f"Failed to fetch submodule data for {submodule}")

        # Copy static files
        os.makedirs('.github/workflows', exist_ok=True)
        shutil.copy2('../static_files/gitTagging.yml', '.github/workflows/gitTagging.yml')
        shutil.copy2('../static_files/PULL_REQUEST_TEMPLATE.md', '.github/PULL_REQUEST_TEMPLATE.md')
        if provider == 'google':
            shutil.copy2('../static_files/test-module-gcp.yml', '.github/workflows/test-module-gcp.yml')
        elif provider == 'aws':
            shutil.copy2('../static_files/test-module-aws.yml', '.github/workflows/test-module-aws.yml')
        shutil.copy2('../static_files/GitVersion.yml', 'GitVersion.yml')
        shutil.copy2('../static_files/README.md', 'README.md')

        if provider == 'google':
            test_module_file = '.github/workflows/test-module-gcp.yml'
        elif provider == 'aws':
            test_module_file = f'.github/workflows/test-module-aws.yml'

        with open(test_module_file, 'r') as f:
            content = f.read()

        # Perform the replacement
        replacements = {
            '%module_name%': module_name,
            '%tf_state_file_identifier%': f'"{provider}_{module_name}"',
            '%work_dir%': f'"examples/{module_name}"',
            '%test_dir%': '"test"',
            '%region%': '"us-east-1"'
        }

        for old, new in replacements.items():
            content = content.replace(old, new)

        # Write the updated content
        with open(test_module_file, 'w') as f:
            f.write(content)

        # Update README
        with open('README.md', 'r') as f:
            content = f.read()

        # Perform the replacement
        replacements = {
            '%human_url%': f"https://registry.terraform.io/modules/{namespace}/{tf_module_name}/{provider}/{version}",
            '%api_endpoint%': f"https://registry.terraform.io/v1/modules/{namespace}/{tf_module_name}/{provider}/{version}",
        }

        for old, new in replacements.items():
            content = content.replace(old, new)

        # Write the updated content
        with open('README.md', 'w') as f:
            f.write(content)


if __name__ == '__main__':
    import sys
    arr = sys.argv[1::]
    if len(arr) == 0:
        print("Local execution with default values")
        # Module details GCP
        namespace = "terraform-google-modules"
        tf_module_name = "cloud-storage"
        module_name = "cloud_storage"
        provider = "google"
        version = "5.0.0"

        # Module details GCP
        namespace = "terraform-aws-modules"
        tf_module_name = "ecr"
        module_name = "ecr"
        provider = "aws"
        version = "2.2.0"
        create_repo(namespace, tf_module_name, module_name, provider, version)

    else:
        print("Cloud execution:")
        print(arr)
        namespace = arr[0]
        tf_module_name = arr[1]
        module_name = arr[2]
        provider = arr[3]
        version = arr[4]
        create_repo(namespace, tf_module_name, module_name, provider, version)
