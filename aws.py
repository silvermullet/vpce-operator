import kubernetes
import yaml
import os
import boto3
import kopf
import logging
import time
from kubernetes.client.rest import ApiException
from botocore.exceptions import ClientError


class SecurityGroup:
    def __init__(self, name, namespace, vpc_id, **kwargs):
        self.name = name
        self.namespace = namespace
        self.security_groups = []
        self.vpc_id = vpc_id
        self.region = kwargs.get("region", "us-west-2")

    def create_security_group(self):
        """Create an open security group for private network RFCs"""
        client = boto3.client('ec2', region_name=self.region)

        try:
            response = client.create_security_group( # noqa
                Description='Generic security group for private network RFCs',
                GroupName=f'{self.name}-generic',
                VpcId=self.vpc_id,
                DryRun=False,
            )
        except ClientError as e:
            raise kopf.PermanentError(
                f"Error creating generic securit group: {e}"
                )

        try:
            logging.info(f"Tagging resource_id: {response['GroupId']}")
            client.create_tags(
                DryRun=False,
                Resources=[response['GroupId']],
                Tags=[
                    {
                        'Key': 'Name',
                        'Value': f"{self.name}-{self.namespace}"
                    },
                ])
        except ClientError as e:
            raise kopf.TemporaryError(
                  f"Failed to tag resouce: {response['GroupId']}: {e}"
                  )

        return response['GroupId']

    def authorize_security_group_ingress(
            self, security_group_id, to_port,
            from_port, ip_ranges, ip_protocol):
        """Update security group ingress"""
        client = boto3.client('ec2', region_name=self.region)

        client.authorize_security_group_ingress(
            DryRun=False,
            GroupId=security_group_id,
            IpPermissions=[
                {
                    'FromPort': from_port,
                    'ToPort': from_port,
                    'IpProtocol': ip_protocol,
                    'IpRanges': ip_ranges
                }
            ]
        )

    def authorize_security_group_egress(
            self, security_group_id, to_port,
            from_port, ip_ranges, ip_protocol):
        """Update security group egress"""
        client = boto3.client('ec2', region_name=self.region)

        client.authorize_security_group_egress(
            DryRun=False,
            GroupId=security_group_id,
            IpPermissions=[
                {
                    'FromPort': from_port,
                    'ToPort': from_port,
                    'IpProtocol': ip_protocol,
                    'IpRanges': ip_ranges
                }
            ]
        )

    def delete_security_group(self, security_group_id):
        logging.info(f"Deleting generated security group: {security_group_id}")
        client = boto3.client('ec2', region_name=self.region)
        client.delete_security_group(
            GroupId=security_group_id,
        )


class VPCe:
    def __init__(
            self, name, namespace, vpc_id,
            vpc_endpoint_service_id, subnet_ids,
            security_groups, **kwargs):

        self.vpce_dns = ""
        self.name = name
        self.namespace = namespace
        self.vpc_id = vpc_id
        self.vpc_endpoint_service_id = vpc_endpoint_service_id
        self.subnet_ids = subnet_ids
        self.security_groups = security_groups
        self.region = kwargs.get("region", "us-west-2")
        self.vpce_aws_resource_id = kwargs.get("vpce_aws_resource_id")

    def create_endpoint(self):
        client = boto3.client('ec2', region_name=self.region)
        resource_id = ""
        try:
            response = client.create_vpc_endpoint(
                DryRun=False,
                VpcEndpointType='Interface',
                VpcId=self.vpc_id,
                ServiceName=self.vpc_endpoint_service_id,
                SubnetIds=self.subnet_ids,
                SecurityGroupIds=self.security_groups,
                PrivateDnsEnabled=False
            )
            logging.info(f"VPC endpoint created: %s", response)
            resource_id = response['VpcEndpoint']['VpcEndpointId']
        except ClientError as e:
            raise kopf.PermanentError(f"Error creating vpc endpoint: {e}")

        try:
            logging.info(f"Tagging resource_id: {resource_id}")
            client.create_tags(
                DryRun=False,
                Resources=[resource_id],
                Tags=[
                    {
                        'Key': 'Name',
                        'Value': f"{self.name}-{self.namespace}"
                    },
                ])
        except ClientError as e:
            raise kopf.TemporaryError(
                  f'Failed to tag resouce: {resource_id}: {e}'
                  )

        self.vpce_dns = response['VpcEndpoint']['DnsEntries'][0]['DnsName']

        return {
            'vpce_aws_resource_id': resource_id,
            'vpce_aws_vpce_dns': self.vpce_dns,
            'vpce_aws_endpoint_status': 'created',
            }

    def delete_endpoint(self):
        client = boto3.client('ec2', region_name=self.region)

        try:
            response = client.delete_vpc_endpoints(
                VpcEndpointIds=[
                    self.vpce_aws_resource_id
                ]
            )
            logging.info(f"VPC endpoint deleted: %s", response)
        except ClientError as e:
            raise kopf.PermanentError(f"Error deleting vpc endpoint: {e}")
        return {
            'vpce_aws_endpoint_status': 'deleted',
            }

    def wait_for_deletion(self):
        client = boto3.client('ec2', region_name=self.region)
        endpoint_state = None
        logging.info(f"Waiting for deletion of endpoint: {self.name}")

        while endpoint_state != 'Deleted':
            try:
                response = client.describe_vpc_endpoints(
                    DryRun=False,
                    VpcEndpointIds=[
                        self.vpce_aws_resource_id,
                    ],
                )
            except ClientError as e:
                if e.response['Error']['Code'] == 'InvalidVpcEndpointId.NotFound': # noqa
                    logging.info(f"Endpoint is deleted")
                    endpoint_state = "Deleted"
                    break

            endpoint_state = response['VpcEndpoints'][0]['State']
            logging.info(
                    f"""
                    Endpoint {self.vpce_aws_resource_id}: {endpoint_state}
                    """
            )
            time.sleep(5)


class K8s:
    def __init__(
            self, name, namespace, **kwargs):
        self.name = name
        self.namespace = namespace
        self.vpce_dns = kwargs.get('vpce_dns')

    def create_k8s_service(self):
        """load svc.yaml and input the data that"""
        path = os.path.join(os.path.dirname(__file__), 'svc.yaml')

        try:
            tmpl = open(path, 'rt').read()
            text = tmpl.format(
                    name=self.name, namespace=self.namespace,
                    vpce_dns=self.vpce_dns
                    )
        except OSError as err:
            logging.error(f"OS error: {err}")

        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as e:
            logging.error(f"Yaml load error: {e}")

        try:
            logging.info(f"SVC body to be sent to k8s: {data}")
            api = kubernetes.client.CoreV1Api()
            obj = api.create_namespaced_service(
                namespace=self.namespace,
                body=data,
            )
            logging.info(f"SVC child is created: %s", obj)
        except ApiException as e:
            raise kopf.PermanentError(f"Error creating svc endpoint: {e}")

        return {
            'svc_endpoint_status': "created"
        }

    def delete_k8s_service(self):
        try:
            logging.info(f"Deleting service: {self.name}")
            api = kubernetes.client.CoreV1Api()
            obj = api.delete_namespaced_service(
                name=self.name,
                namespace=self.namespace,
            )
            logging.info(f"SVC deleted: %s", obj)
        except ApiException as e:
            raise kopf.PermanentError(f"Error deleting svc endpoint: {e}")

        return {
            'svc_endpoint_status': "deleted"
        }
