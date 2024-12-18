import rpc
from jinja2 import Environment, FileSystemLoader, Template
from sys import argv
import re
import xml.etree.ElementTree as ET
# Input variables: device, username, password, original_port, new_east_port, new_west_port
#Args to vars
tid = argv[1]
un = argv[2]
pw = argv[3]
original_port = argv[4]
new_east_port = argv[5]
new_west_port = argv[6]
if len(argv) != 7:
    print("Please review your input args.")
    exit

#Class to represent flowpoint objects that will be instanced from the XML we query from the device
class Flowpoint:
    def __init__(self, name, fd_name, log_port, push_vid):
        self.name = name
        self.fd_name = fd_name
        self.log_port = log_port
        self.push_vid = push_vid
    def __repr__(self):
        return f"flowpoint(name={self.name}, fd_name={self.fd_name}, log_port={self.log_port}, push_vid={self.push_vid})"

# Error handling to verify whether a Child Element exists. Necessary for FDs with no description, which otherwise throw XML parsing errors.
def hasChildElement(parent, child_tag):
    return parent.find(child_tag) is not None

#Regex to replace the port numbers from original flowpoint to new FPs
def re_patterns(re_fp_name, new_port):
    pattern1 = r"_\d_\d"
    pattern2 = r"\d{2}_"
    pattern3 = r"\d{1}_"

    #tries pattern1, if no change, tries pattern2, etc
    new_fp_name = re.sub(pattern1, new_port + "_", re_fp_name, count=1)
    if new_fp_name == re_fp_name:
        new_fp_name = re.sub(pattern2, new_port + "_", re_fp_name, count=1)
        if new_fp_name == re_fp_name:
            new_fp_name = re.sub(pattern3, new_port + "_", re_fp_name, count=1)
            if new_fp_name == re_fp_name:
                print("failure during regex on FP names")
                exit
    return new_fp_name

# Create xml trees from strings returned by NETCONF for FPs and FDs
def parseXml(fpstring, fdstring):
    #Creating a dictionary of namespaces to reference instead of writing them in for each .find
    ns = {'nc_base': 'urn:ietf:params:xml:ns:netconf:base:1.0',
        'ciena_fp': 'urn:ciena:params:xml:ns:yang:ciena-pn:ciena-mef-fp',
        'ciena_fd': 'urn:ciena:params:xml:ns:yang:ciena-pn:ciena-mef-fd'}

    #Creating empty list and dictionary to add flowpoint and forwarding domain objects to 
    flowpoints = []
    forwarding_domains = {}

    #Working through the XML tree for FLOW POINT level-by-level to get to the interesting data
    fp_root = ET.fromstring(fpstring)
    data_elem = fp_root.find('nc_base:data', ns)
    fps_elem = data_elem.find('ciena_fp:fps', ns)
    #Looping through each FP branch in the tree and creating variables for the children we are interested in
    for fp_elem in fps_elem.findall('ciena_fp:fp', ns):
        fp_name = fp_elem.find('ciena_fp:name', ns).text
        fd_name = fp_elem.find('ciena_fp:fd-name', ns).text
        log_port = fp_elem.find('ciena_fp:logical-port', ns).text
        #Using try to avoid script failure when an FP doesn't have the XML spine for push-vid.
        try:
            egress_l2_trans = fp_elem.find('ciena_fp:egress-l2-transform', ns)
            vlan_stack = egress_l2_trans.find('ciena_fp:vlan-stack', ns)
            #Instantiates a Flowpoint class object only if the FP has a VLAN tag and matches the queried port
            if hasChildElement(vlan_stack, '{urn:ciena:params:xml:ns:yang:ciena-pn:ciena-mef-fp}push-vid') and (log_port == original_port):
                push_vid = vlan_stack.find('ciena_fp:push-vid', ns).text
                flowpoint = Flowpoint(fp_name, fd_name, log_port, push_vid)
                flowpoints.append(flowpoint) 
            elif hasChildElement(fp_elem, '{urn:ciena:params:xml:ns:yang:ciena-pn:ciena-mef-fp}push-vid'):
                print(f"flow {fp_name} is being IGNORED -- matched on push-vid only")
            elif log_port == original_port:
                print(f"flow {fp_name} is being IGNORED -- matched log_port only")
            else:
                print(f"flow {fp_name} is being IGNORED -- VLAN is untagged and port does not match query")
        except:
            print(f"{fp_name} is being IGNORED -- failed try/except")

    #Working through the XML tree for FORWARDING DOMAIN level-by-level to get to the interesting data
    fd_root = ET.fromstring(fdstring)
    fds_elem = fd_root.find('nc_base:data', ns)
    fds = fds_elem.find('ciena_fd:fds', ns)
    #Looping through each fd branch in the tree and creating variables for the children we are interested in
    for fd_elem in fds.findall('ciena_fd:fd', ns):
        fd_name = fd_elem.find('ciena_fd:name', ns).text

        # If/Else to determine if a description exists for an FD, otherwise a 'No desc' string is added for that value
        if hasChildElement(fd_elem, '{urn:ciena:params:xml:ns:yang:ciena-pn:ciena-mef-fd}description'):
            fd_desc = fd_elem.find('ciena_fd:description', ns).text
            forwarding_domains[fd_name]=fd_desc
        else:
            forwarding_domains[fd_name]='No desc'

    addObjAttributes(flowpoints, forwarding_domains, original_port)

#Adds the needed attributes to our objects
def addObjAttributes(flowpoints, forwarding_domains, port):
    for flow in flowpoints:
        fdname = flow.fd_name
        new_east_fp_name = re_patterns(flow.name, new_east_port)
        new_west_fp_name = re_patterns(flow.name, new_west_port)
        setattr(flow, 'fd_desc', forwarding_domains[fdname])
        setattr(flow, 'new_east_fp_name', new_east_fp_name)
        setattr(flow, 'new_west_fp_name', new_west_fp_name)

    parseJinja(flowpoints)

# Loop through FP objects, pass the attr's into the template, append the output to
# a local file
def parseJinja(flows_for_jinja):
    environment = Environment(loader=FileSystemLoader("templates/"))
    template = environment.get_template("service.txt")

    for service_data in flows_for_jinja:
        content = template.render(log_port_east=new_east_port, log_port_west=new_west_port, vlan=service_data.push_vid, fd_name=service_data.fd_name, fd_desc=service_data.fd_desc, fp_name_east=service_data.new_east_fp_name, fp_name_west=service_data.new_west_fp_name)
        with open('output.txt', mode="a", encoding="utf-8") as message:
            message.write(content)
            print(f"Added config for {service_data.fd_name}")

#Calls the RPC module for FDs and FPs, passes the reply on to the XML parser as strings
def main():
    nc_xml_fp = rpc.rpcGetFps(tid, un, pw)
    nc_xml_fd = rpc.rpcGetFds(tid, un, pw)
    xml_fp_raw = nc_xml_fp._raw
    xml_fd_raw = nc_xml_fd._raw

    parseXml(xml_fp_raw, xml_fd_raw)

if __name__ == "__main__":
    main()