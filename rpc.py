from ncclient import manager

filter_engineId = '''
            <snmp xmlns=\"urn:ietf:params:xml:ns:yang:ietf-snmp\">
                <engine>
                    <engine-id/>
                </engine>
            </snmp>
            '''
filter_fds = '''
            <fds xmlns=\"urn:ciena:params:xml:ns:yang:ciena-pn:ciena-mef-fd\">
            </fds>
            '''
filter_fps = '''
            <fps xmlns=\"urn:ciena:params:xml:ns:yang:ciena-pn:ciena-mef-fp\">
            </fps>
            '''
def rpcGetFps(tid, un, pw):

    with manager.connect(host=tid, port=830, username=un, password=pw, hostkey_verify=False) as m:
        c = m.get_config(source = 'running', filter =('subtree', filter_fps))
    return(c)
def rpcGetFds(tid, un, pw):

    with manager.connect(host=tid, port=830, username=un, password=pw, hostkey_verify=False) as m:
        c = m.get_config(source = 'running', filter =('subtree', filter_fds))
    return(c)
