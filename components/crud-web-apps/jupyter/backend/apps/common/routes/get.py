from kubernetes import client
import re
from kubeflow.kubeflow.crud_backend import api, logging

from .. import utils
from . import bp
import requests

log = logging.getLogger(__name__)


@bp.route("/api/config")
def get_config():
    config = utils.load_spawner_ui_config()
    return api.success_response("config", config)


@bp.route("/api/namespaces/<namespace>/pvcs")
def get_pvcs(namespace):
    pvcs = api.list_pvcs(namespace).items
    data = [{"name": pvc.metadata.name,
             "size": pvc.spec.resources.requests["storage"],
             "mode": pvc.spec.access_modes[0]} for pvc in pvcs]

    return api.success_response("pvcs", data)


@bp.route("/api/namespaces/<namespace>/poddefaults")
def get_poddefaults(namespace):
    pod_defaults = api.list_poddefaults(namespace)

    # Return a list of (label, desc) with the pod defaults
    contents = []
    for pd in pod_defaults["items"]:
        label = list(pd["spec"]["selector"]["matchLabels"].keys())[0]
        if "desc" in pd["spec"]:
            desc = pd["spec"]["desc"]
        else:
            desc = pd["metadata"]["name"]

        contents.append({"label": label, "desc": desc})

    log.info("Found poddefaults: %s", contents)
    return api.success_response("poddefaults", contents)


@bp.route("/api/namespaces/<namespace>/notebooks")
def get_notebooks(namespace):
    notebooks = api.list_notebooks(namespace)["items"]
    contents = [utils.notebook_dict_from_k8s_obj(nb) for nb in notebooks]

    return api.success_response("notebooks", contents)


@bp.route("/api/gpus")
def get_gpu_vendors():
    """
    Return a list of GPU vendors for which at least one node has the necessary
    annotation required to schedule pods
    """
    print('***************** Get Server GPU Resource *******************')
    frontend_config = utils.load_spawner_ui_config()
    gpus_value = frontend_config.get("gpus", {}).get("value", {})
    config_vendor_keys = [
        v.get("limitsKey", "") for v in gpus_value.get("vendors", [])
    ]
# from kubernetes import client, config
# import re
# config.load_kube_config()
    autoscaler_status = {"node_group": {}}
    v1 = client.CoreV1Api()
    try:
        configmap = v1.read_namespaced_config_map(name="cluster-autoscaler-status", namespace="kube-system")
        autoscaler_status["node_group"] = autoscaler_configmap_parser(configmap)
    except client.rest.ApiException as e:
        if e.status == 404:
            print("Configmap does not exist")
        else:
            # TODO Modify ClusterRole/jupyter-web-app-cluster-role configmaps
            print("Error:", e.reason)  

# read available gpu num from dcgm 
    try:
        dcgm_endpoints = v1.read_namespaced_endpoints(name="nvidia-dcgm-exporter", namespace="gpu-operator")
        dcgm_gpu_info = dcgm_endpoints_parser(dcgm_endpoints)
        print('dcgm_gpu_info: ', dcgm_gpu_info)
    except client.rest.ApiException as e:
        if e.status == 404:
            print("DCGM Endpoints does not exist")
        else:
            # TODO Modify ClusterRole/jupyter-web-app-cluster-role endpoints
            print("Error:", e.reason)

    # Get all of the different resources installed in all nodes
    installed_resources = set()
    nodes = api.list_nodes().items
    # {
    #     "GRID-V100-8C": {
    #         "capacity_per_node": "1", 
    #         "total_capacity": "2", 
    #         "total_available": "1",
    #         "autoscaler_enable": True,
    #         "autoscaler_min_size": 1,
    #         "autoscaler_max_size": 4,
    #         "autoscaler_cloud_provider_target": 2,
    #     },
    #     "GRID-V100-4C": {
    #         "capacity_per_node": "1", 
    #         "total_capacity": "1", 
    #         "total_available": "1",
    #         "autoscaler_enable": True,
    #         "autoscaler_min_size": 1,
    #         "autoscaler_max_size": 4,
    #         "autoscaler_cloud_provider_target": 1,
    #     }
    # }
    gpu_info = {}

    for node in nodes:
        print('*/' * 20)
        print('node name: ', node.metadata.name)
        print('node info: ', node.status.capacity)
        NFD_LABEL_PRODUCT = "nvidia.com/gpu.product" 
        NFD_LABEL_COUNT = "nvidia.com/gpu.count"
        if NFD_LABEL_PRODUCT in node.metadata.labels:
            gpu_product = node.metadata.labels[NFD_LABEL_PRODUCT]
            print('gpu_product: ', gpu_product)
            gpu_info[gpu_product] = gpu_info.get(gpu_product, {})
            gpu_info[gpu_product]["capacity_per_node"] = int(node.metadata.labels[NFD_LABEL_COUNT])
            gpu_info[gpu_product]["total_capacity"] = gpu_info[gpu_product].get("total_capacity", 0) + int(node.metadata.labels[NFD_LABEL_COUNT])            
            machine_deployment_name = "-".join(node.metadata.name.split("-")[:-2])
            if machine_deployment_name in autoscaler_status['node_group']:
                gpu_info[gpu_product]['autoscaler_enable'] = True
                gpu_info[gpu_product]['autoscaler_cloud_provider_target'] = autoscaler_status['node_group'][machine_deployment_name]['cloudProviderTarget']
                gpu_info[gpu_product]['autoscaler_min_size'] = autoscaler_status['node_group'][machine_deployment_name]['min_size']
                gpu_info[gpu_product]['autoscaler_max_size'] = autoscaler_status['node_group'][machine_deployment_name]['max_size']

            gpu_info[gpu_product]["total_available"] = dcgm_gpu_info[gpu_product]

        print('node nfd info: ', gpu_info)
        installed_resources.update(node.status.capacity.keys())  

    # Keep the vendors the key of which exists in at least one node
    available_vendors = installed_resources.intersection(config_vendor_keys)
    print('available_vendors: ', available_vendors)

    data_field = ["vendors", "gpuslist"]
    data = [list(available_vendors), gpu_info]

    print('&' * 20)
    print('api.success_response_2', api.success_response_2(data_field, data))
    print('type: ', type(api.success_response_2(data_field, data)))

    

    return api.success_response_2(data_field, data)


# @bp.route("/api/gpus")
# def get_gpu_vendors():
#     """
#     Return a list of GPU vendors for which at least one node has the necessary
#     annotation required to schedule pods
#     """
#     print('***************** Get Server GPU List *******************')
#     frontend_config = utils.load_spawner_ui_config()
#     gpus_value = frontend_config.get("gpus", {}).get("value", {})
#     config_vendor_keys = [
#         v.get("limitsKey", "") for v in gpus_value.get("vendors", [])
#     ]

#     # Get all of the different resources installed in all nodes
#     installed_resources = set()
#     nodes = api.list_nodes().items
    
#     for node in nodes:
#         print('node name: ', node.metadata.name)
#         print('node info: ', node.status.capacity)
#         nfd_label = "nvidia.com/gpu.product" 
#         if nfd_label in node.metadata.labels:
#             print('node nfd label: nvidia.com/gpu.product: ' + node.metadata.labels["nvidia.com/gpu.product"] + ', nvidia.com/gpu.memory: ' + node.metadata.labels["nvidia.com/gpu.memory"])
        
#         installed_resources.update(node.status.capacity.keys())  # !!! important

#     # Keep the vendors the key of which exists in at least one node
#     available_vendors = installed_resources.intersection(config_vendor_keys)
#     print('available_vendors: ', available_vendors)

#     return api.success_response("vendors", list(available_vendors))

# {
#     'clusterclass-jinheng-gpuworkers-4g-cp85k': {
#         'namespace': 'tkg-ns-auto', 
#         'ready': '2', 
#         'cloudProviderTarget': '2', 
#         'min_size': '1', 
#         'max_size': '4', 
#         'ScaleUp_activity': 'NoActivity', 
#         'ScaleUp_ready': '2', 
#         'ScaleUp_cloudProviderTarget': '2', 
#         'ScaleDown_activity': 'NoCandidates', 
#         'ScaleDown_candidates': '0'
#         }, 
#     'clusterclass-jinheng-gpuworkers-8g-tgsfv': {
#         'namespace': 'tkg-ns-auto', 
#         'ready': '1', 
#         'cloudProviderTarget': '1', 
#         'min_size': '1', 
#         'max_size': '4', 
#         'ScaleUp_activity': 'NoActivity', 
#         'ScaleUp_ready': '1', 
#         'ScaleUp_cloudProviderTarget': '1', 
#         'ScaleDown_activity': 'NoCandidates', 
#         'ScaleDown_candidates': '0'
#         }
# }
def autoscaler_configmap_parser(configmap):
    AUTOSCALER_STATUS_NODEGROUP_LENGTH = 10
    autoscaler_status_array = [x for x in configmap.data['status'].split('\n') if x != '']
    node_group_number = int((len(autoscaler_status_array) - 1 - autoscaler_status_array.index("NodeGroups:")) / AUTOSCALER_STATUS_NODEGROUP_LENGTH)
    node_groups = {}
    for i in range(node_group_number):
        node_group = {}
        node_group_init_index = autoscaler_status_array.index("NodeGroups:") + 1 + i * AUTOSCALER_STATUS_NODEGROUP_LENGTH
        # '  Name:        MachineDeployment/tkg-ns-auto/clusterclass-jinheng-gpuworkers-4g-cp85k'
        regexp = re.compile(r'^\s*Name:\s+MachineDeployment\/(?P<namespace>.*?)\/(?P<machine_deployment>.*?)$')
        re_match = regexp.match(autoscaler_status_array[node_group_init_index])
        node_groups[re_match.group('machine_deployment')] = node_group
        node_group['namespace'] = re_match.group('namespace')
        # '  Health:      Healthy (ready=2 unready=0 (resourceUnready=0) notStarted=0 longNotStarted=0 registered=2 longUnregistered=0 cloudProviderTarget=2 (minSize=1, maxSize=4))'
        regexp = re.compile(r'^\s*Health:\s+Healthy \(ready=(?P<ready>.*?) unready=(?P<unready>.*?) \(resourceUnready=(?P<resourceUnready>.*?)\) notStarted=(?P<notStarted>.*?) longNotStarted=(?P<longNotStarted>.*?) registered=(?P<registered>.*?) longUnregistered=(?P<longUnregistered>.*?) cloudProviderTarget=(?P<cloudProviderTarget>.*?) \(minSize=(?P<minSize>.*?), maxSize=(?P<maxSize>.*?)\)\)$')
        re_match = regexp.match(autoscaler_status_array[node_group_init_index + 1])
        node_group['ready'] = re_match.group('ready')
        node_group['cloudProviderTarget'] = re_match.group('cloudProviderTarget')
        node_group['min_size'] = re_match.group('minSize')
        node_group['max_size'] = re_match.group('maxSize')
        # '  ScaleUp:     NoActivity (ready=2 cloudProviderTarget=2)'
        regexp = re.compile(r'^\s*ScaleUp:\s+(?P<activity>.*?) \(ready=(?P<ready>.*?) cloudProviderTarget=(?P<cloudProviderTarget>.*?)\)$')
        re_match = regexp.match(autoscaler_status_array[node_group_init_index + 4])
        node_group['ScaleUp_activity'] = re_match.group('activity')
        node_group['ScaleUp_ready'] = re_match.group('ready')
        node_group['ScaleUp_cloudProviderTarget'] = re_match.group('cloudProviderTarget')
        # '  ScaleDown:   NoCandidates (candidates=0)'
        regexp = re.compile(r'^\s*ScaleDown:\s+(?P<activity>.*?) \(candidates=(?P<candidates>.*?)\)$')
        re_match = regexp.match(autoscaler_status_array[node_group_init_index + 7])
        node_group['ScaleDown_activity'] = re_match.group('activity')
        node_group['ScaleDown_candidates'] = re_match.group('candidates')
    print(node_groups)
    return node_groups

def dcgm_endpoints_parser(dcgm_endpoints):
    print('/@'*30)
    ip_addresses = []
    total_gpu = 0
    available_gpu = 0
    dcgm_info = []
    available_gpu = {}
    # ip_port = dcgm_endpoints.subsets[0].ports[0].port

    for address in dcgm_endpoints.subsets[0].addresses:
        ip_addresses.append(address.ip)
        ip_address = address.ip

        url = "http://" + ip_address + ":9400/metrics"
        headers = {"Accept": "text/plain"}
        response = requests.get(url, headers=headers)
        raw_info = response.content.decode().split("\n")

        for line in raw_info:
            if line.startswith("DCGM_FI_DEV_FB_USED"):
                regexp = re.compile(r'DCGM_FI_DEV_FB_USED{gpu="(?P<gpu>.*?)",UUID="(?P<UUID>.*?)",device="(?P<device>.*?)",modelName="(?P<modelName>.*?)",Hostname="(?P<Hostname>.*?)",DCGM_FI_DRIVER_VERSION="(?P<DCGM_FI_DRIVER_VERSION>.*?)",container="(?P<container>.*?)",namespace="(?P<namespace>.*?)",pod="(?P<pod>.*?)"}.*')
                re_match = regexp.match(line)
                if re_match.group("pod") == "":
                    available_num = 1
                else:
                    available_num = 0
                dcgm_info.append({
                    "gpu":  re_match.group("gpu"),
                    "UUID":  re_match.group("UUID"),
                    "device":  re_match.group("device"),
                    "modelName":  re_match.group("modelName"),
                    "Hostname":  re_match.group("Hostname"),
                    "DCGM_FI_DRIVER_VERSION":  re_match.group("DCGM_FI_DRIVER_VERSION"),
                    "container":  re_match.group("container"),
                    "namespace":  re_match.group("namespace"),
                    "pod":  re_match.group("pod"),
                    "avilable_num": available_num
                })

    for item in dcgm_info:
        modelName = item['modelName'].replace(' ', '-')
        available_gpu[modelName] = available_gpu.get(modelName, 0) + item['avilable_num']

    return available_gpu