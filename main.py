#!/usr/bin/python

import argparse
import http.client
import json
import logging
import os

logging.basicConfig(level=logging.INFO)


def early_exit(reason, level=logging.ERROR):
    logging.log(level, reason)
    exit(0 if level <= logging.INFO else 1)


def parse_args():
    parser = argparse.ArgumentParser(description='CloudFlare DDNS')
    parser.add_argument('-c', '--config', type=argparse.FileType('r'), required=True)
    return parser.parse_args()


def get_config(config):
    try:
        return json.loads(config.read())
    except:
        return None
    finally:
        config.close()


def get_ipv4():
    try:
        conn = http.client.HTTPConnection("ifconfig.me")
        conn.request("GET", "/ip", "")
        return conn.getresponse().read().decode("utf-8")
    except:
        return None
    finally:
        conn.close()


def is_new_ipv4(ipv4):
    if os.path.isfile("ipv4.txt"):
        ipv4_file = open("ipv4.txt", "r")
        old_ipv4 = ipv4_file.read()
        ipv4_file.close()
        if ipv4 == old_ipv4:
            return False

    ipv4_file = open("ipv4.txt", "w")
    ipv4_file.write(ipv4)
    ipv4_file.close()
    return True


def get_xauth(config):
    return {
        'x-auth-email': config["auth"]["email"],
        'x-auth-key': config["auth"]["key"]
    }


def cloudflare_url(*args, **kwargs):
    try:
        conn = http.client.HTTPSConnection("api.cloudflare.com")
        conn.request(*args, **kwargs)
        return json.loads(conn.getresponse().read())
    except:
        return None
    finally:
        conn.close()


def get_cloudflare_zone_identifier(xauth_header, zone):
    try:
        url = "/client/v4/zones?name=%s" % zone
        return cloudflare_url("GET", url, "", xauth_header)["result"][0]["id"]
    except (KeyError, TypeError):
        return None


def get_cloudflare_record_identifier(xauth_header, zone_id, record_name):
    try:
        url = "/client/v4/zones/%s/dns_records?name=%s" % (zone_id, record_name)
        return cloudflare_url("GET", url, "", xauth_header)["result"][0]["id"]
    except (KeyError, TypeError):
        return None


def push_cloudflare_record(xauth_header, zone_id, record_id, record_name, ipv4):
    try:
        url = "/client/v4/zones/%s/dns_records/%s" % (zone_id, record_id)
        data = json.dumps({"id": zone_id, "type": "A", "name": record_name, "proxied": True, "content": ipv4})
        return cloudflare_url("PUT", url, data, xauth_header)["success"]
    except (KeyError, TypeError):
        return False


def main():
    args = parse_args()

    config = get_config(args.config)
    if not config:
        early_exit("could not properly load config file, exiting")

    ipv4 = get_ipv4()
    if not ipv4:
        early_exit("could not fetch ipv4 address, exiting")

    logging.info("current IP address: %s" % ipv4)
    if not is_new_ipv4(ipv4):
        early_exit("ipv4 not changed, exiting", logging.INFO)

    xauth_header = get_xauth(config)
    zone_identifier = get_cloudflare_zone_identifier(xauth_header, config["zone"]["name"])
    if not zone_identifier:
        early_exit("could not fetch zone identifier, exiting")

    for record in config["zone"]["records"]:
        record_identifier = get_cloudflare_record_identifier(xauth_header, zone_identifier, record)
        if record_identifier and push_cloudflare_record(xauth_header, zone_identifier, record_identifier, record, ipv4):
            logging.info("ip changed to %s for zone record %s" % (ipv4, record))
        else:
            logging.error("api update failed for zone record %s" % record)


if __name__ == "__main__":
    main()
