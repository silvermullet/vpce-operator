# AWS vpce-operator

The __Vpce Operator__ manages the deployment of AWS VPC Endpoints and supporting Kubernetes Service [ExternalNames](https://kubernetes.io/docs/concepts/services-networking/service/#externalname). It is built on top of the [Kopf](https://github.com/zalando-incubator/kopf) framework.

The project is currently in beta (`v1beta1`), and while we do not anticipate changing the API in backwards-incompatible ways there is no such guarantee yet.

## Menu

- [Getting Started](#getting-started)
    - [Requirements](#requirements)
    - [Helm Chart](#helm-chart)
    - [Generated Generic Security Groups for VPCe](#generated-generic-security-group)
    - [Provided Security Groups for VPCe](#provided-security-groups)
    - [Future Support](#future-support)
    - [Local Development Setup](#local-development-setup)
    - [Build a Docker Image for vpce-operator](#build-a-docker-image-for-vpce-operator)

Minimal IAM role:
```bash
# todo
```

Values yaml to provide to helm chart in values.yaml:
```bash
namespace: default

podAnnotations:
  iam.amazonaws.com/role: <role_arn_provided_by_user>
```

## Helm Chart

[vpce-operator-helm-chart](https://github.com/silvermullet/vpce-operator-helm-chart)

Install Helm repo
```bash
helm repo add vpce-operator https://silvermullet.github.io/vpce-operator-helm-chart/
helm search vpce-operator
```

Install vpce-opertor with via helm with some provided values
```bash
helm upgrade --install vpce-operator vpce-operator --values values.yaml --namespace default
```

## Generated Generic Security Groups for VPCe

This request to the operator will create a VPC Endpoint within the provided vpc_id and subnet-ids. The security groups will be generated
to provide full access for private network RFCs 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 for all network protocols and also and open egress.

```yaml
apiVersion: silvermullet.com/v1beta1
kind: VPCEndpoint
metadata:
  name: external-service-endpoint-generic-generated-sg 
  namespace: external
spec:
  region: us-west-2
  vpc_endpoint_service_id: com.amazonaws.vpce.us-west-2.vpce-svc-0abc437c186123456
  security_group_type: generated
  vpc_id: vpc-01393d9ccb6d12345
  subnet_ids:
    - subnet-07e56cb8d19c12345
    - subnet-030aa367b20323456
    - subnet-03312c20bc5034567
```

```bash
$ kubectl get vpce
NAME                                             AGE
external-service-endpoint-generic-generated-sg   19s
```

```bash
$ kubectl describe vpce external-service-endpoint-generic-generated-sg
Name:         external-service-endpoint-generic-generated-sg
Namespace:    default
Labels:       <none>
Annotations:  kopf.zalando.org/last-handled-configuration:
                {"spec": {"region": "us-west-2", "security_group_type": "generated", "subnet_ids": ["subnet-07e56cb8d19c12345", "subnet-030aa367b20312346"...
              kubectl.kubernetes.io/last-applied-configuration:
                {"apiVersion":"silvermullet.com/v1","kind":"VPCEndpoint","metadata":{"annotations":{},"name":"external-service-endpoint-generic-generated-sg","n...
API Version:  silvermullet.com/v1beta1
Kind:         VPCEndpoint
Metadata:
  Creation Timestamp:  2019-10-20T21:56:52Z
  Finalizers:
    kopf.zalando.org/KopfFinalizerMarker
  Generation:        2
  Resource Version:  85472
  Self Link:         /apis/silvermullet.com/v1/namespaces/default/vpcendpoints/external-service-endpoint-generic-generated-sg
  UID:               78453f29-0777-4a5a-b91d-bfc5eb3cef78
Spec:
  Region:               us-west-2
  security_group_type:  generated
  subnet_ids:
    subnet-07e56cb8d19c12345
    subnet-030aa367b20123467
    subnet-03312c20bc3456789
  vpc_endpoint_service_id:  com.amazonaws.vpce.us-west-2.vpce-svc-0abc437c186123456
  vpc_id:                   vpc-01393d9ccb6123456
Status:
  create_fn:
    svc_k8s_obj:               created
    vpce_aws_endpoint_status:  created
    vpce_aws_resource_id:      vpce-07c556c90d3123456
    vpce_aws_vpce_dns:         vpce-07c556c90d3123456-myjib123.vpce-svc-0abc437c186123456.us-west-2.vpce.amazonaws.com
    vpce_security_group:       sg-05d16b9da13123456
  Kopf:
Events:
  Type    Reason   Age   From  Message
  ----    ------   ----  ----  -------
  Normal  Logging  75s   kopf  All handlers succeeded for creation.
  Normal  Logging  75s   kopf  Handler 'create_fn' succeeded.
```

Deleting this vpce resource will delete the VPCE and generated security group that is attached to it.

## Provided Security Groups for VPCe

This request to the operator will use the provided vpc_id, subnet-ids and provided security group (must be a security group attached to the VPC you are creating the VPC Endpoint within). Upon deletion it will not delete the security group provided.

```yaml
apiVersion: silvermullet.com/v1beta1
kind: VPCEndpoint
metadata:
  name: external-service-endpoint-provided-sgs
  namespace: default
spec:
  region: us-west-2
  vpc_endpoint_service_id: com.amazonaws.vpce.us-west-2.vpce-svc-01a99586728a12345
  security_group_type: provided
  security_group_ids:
    - sg-0142d2a79ee273c19
  vpc_id: vpc-01393d9ccb6d12345
  subnet_ids:
    - subnet-07e56cb8d19c12345
    - subnet-030aa367b20323456
    - subnet-03312c20bc5034567
```

## Future support

  * Support for custom generated security groups
  * Support for the creation of PrivateLink Endpoint Services for Ingress VPC traffic


## Local Development Setup

```bash
git clone https://github.com/trulia/vpce-operator.git
cd vpce-operator
pip install poetry
poetry shell
```

## Build a Docker Image for vpce-operator

```bash
docker build . -t <repository>/vpce-operator:<tag>
docker push <repository>/vpce-operator:<tag>
```

## License

Please read the [LICENSE](LICENSE) file here.
