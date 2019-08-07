import asyncio
import websockets
import os
import json
import logging
import aiohttp
import ssl
import proton
from rhmsg.activemq.producer import AMQProducer

async def start():
    # Set log level, default is INFO
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    # Github Branch name from System Variable
    branch_name = os.getenv('GH_BRANCH','')
    # Provided URL for triggering build proccess or starting pipeline from System Variable
    build_url = os.getenv('URL_TRIGGER','')
    # WebSockets Endpoint URL provided from System Variable
    ws_endpoint = os.getenv('WS_SERVER', "")
    # List of Allowed Headers from Github webhooks POST request
    alowed = ["Accept", "User-Agent", "X-Github-Event", "X-Github-Delivery", "Content-Type", "X-Hub-Signature"]
    # UMB certificate files & endpoint
    topic = "VirtualTopic.eng.tightbeam."
    rh_cert = os.getenv("RH_CERT","")
    rh_key = os.getenv("RH_KEY","")
    rh_crt = os.getenv("RH_CRT","")
    amqp_url = os.getenv("AMQP_URL","")
    amqp_topic = os.getenv("AMQP_TOPIC","")
    #SSL connection present:
    print("--- SSL connection present: {}".format(proton.SSL.present()))
    print("--- RH Variables: rh_cert:{}  rh_key:{} rh_crt:{} amqp_url:{} amqp_topic:{}".format(rh_cert,rh_key,rh_crt,amqp_url,topic+amqp_topic))

    # Opening WebSocket Connection to WebSocket server
    async with websockets.connect(ws_endpoint) as websocket:
        logging.info('--- Opened Connection to Server ---')
        # sending websocket message to server
        await websocket.send(json.dumps({'msg':'TEST MESSAGE'}))
        while True:
            # Listening for recived messages from websocket server
            response = await websocket.recv()
            # Connection from websocket server is closed so terminate this iterations
            if response is None:
                logging.warning("Response None. Exit.")
                break
            logRecivedMessage(response) # Log websocket recived message
            data = json.loads(response)
            message = {}
            payload = json.loads(data["payload"])
            message["payload"] = payload
            logRecivedMessagePayload(payload)
            # Create Dictionary of allowed headers from rerouted webhook POST request
            message['headers'] =  {x:y for x,y in data["headers"].items() if x in alowed}
            if "ref" in payload:
                # REF Github branch for building project
                ref = payload["ref"].split("/")[2]
            else:
                logging.info("Not containing ref")
                ref = ''
            # If not specify branches, we accept all
            if branch_name == '' or ref in branch_name.split(","):
                amqp_props = dict()
                amqp_props['subject'] = payload['head_commit']['message']
                amqp_message = str(message)
                producer = AMQProducer(
                    urls=amqp_url,
                    certificate=rh_crt,
                    private_key=rh_key,
                    trusted_certificates=rh_cert,
                    topic=topic+amqp_topic
                )
                # send AMQP message to Red Hat UMB service
                producer.send_msg(amqp_props,amqp_message.encode("utf-8"))
            else:
                logDifferentBranchName(ref,branch_name)

def logRecivedMessage(msg):
    resp_txt = str(msg)
    rspn = json.loads(resp_txt.replace("\'", "\""))
    logging.info("-- New Code Event ID: {}".format(rspn.get('id')))
    logging.info("-- New Code Event Headers: {}".format(rspn.get("headers")))
    logging.info("-- New Code Change {} Event".format(rspn.get("headers").get("X-Github-Event")))

def logRecivedMessagePayload(payload):
    logging.info("-- Payload: {}".format(json.dumps(payload, indent=2)))
    logging.info(payload.get('ref'))
    logging.info(payload.get('pusher'))

async def logResponseMessage(resp,url):
    logging.info('-- Sending HTTP POST to {}'.format(url))
    logging.info(resp.status)
    logging.info(resp.text())

def logGetResponseMessage(resp,url):
    logging.info('-- Sending HTTP GET to {}'.format(url))
    logging.info(resp.status)
    logging.info(resp.text())

def logDifferentBranchName(ref,branch):
    logging.info('-- Branch name {} not in GH_BRANCH ({})'.format(ref, branch))

# Start Non-Blocking thread for Asynchronous Handling of Long Lived Connections
asyncio.get_event_loop().run_until_complete(start())
