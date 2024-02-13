#!/usr/bin/env python3

from aws_cdk import (
    App,
    Stack,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_secretsmanager as secretsmanager,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancingv2_targets as targets,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
)
import json
from constructs import Construct

class FaceMatchingStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # 認証情報のシークレットを作成
        auth_secret = secretsmanager.Secret(self, "AuthSecret",
            secret_name="auth",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps({
                    "username": "loginuser",
                    "password": "loginpassword"
                }),
                generate_string_key="password"
            )
        )

        # IAMロールの作成
        role = iam.Role(
            self, "FaceMatchingInstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com")
        )

        # Secrets Managerへのアクセス権限を追加
        role.add_to_policy(iam.PolicyStatement(
            actions=["secretsmanager:GetSecretValue"],
            resources=["arn:aws:secretsmanager:*:*:secret:*"]
        ))

        # VPCの作成
        vpc = ec2.Vpc(self, 'FaceMatching-VPC',
            cidr='172.16.0.0/16',
            nat_gateways=1,
            availability_zones=['ap-northeast-1a', 'ap-northeast-1c'],
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC,
                    name='Public',
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    name='Private',
                    cidr_mask=24
                )
            ]
        )

        # EC2セキュリティグループの定義
        ec2_sg = ec2.SecurityGroup(
            self, "FaceMatching-EC2-Sg",
            vpc=vpc,
            allow_all_outbound=True,
        )
        ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80))
        ec2_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(5000))  # アプリケーションのポート


        # EC2インスタンスの定義の前にユーザーデータスクリプトを定義
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "sudo dnf update -y",  # システムの更新
            "sudo dnf install -y postgresql15",
            "sudo dnf install -y git docker",  # GitとDockerのインストール
            "sudo systemctl start docker",  # Dockerサービスの開始
            "sudo systemctl enable docker",  # Dockerサービスの自動起動設定
            "sudo usermod -aG docker ec2-user",  # ec2-userをdockerグループに追加
            "export AWS_DEFAULT_REGION=ap-northeast-1",  # AWSのデフォルトリージョンを設定
            "cd /home/ec2-user",
        )

        # EC2インスタンスの定義
        ec2_instance1 = ec2.Instance(
            self, "FaceMatching-EC2",
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ec2.GenericLinuxImage({'ap-northeast-1': 'ami-012261b9035f8f938'}),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            security_group=ec2_sg,
            availability_zone='ap-northeast-1a',
            user_data=user_data, 
            role=role,
            ssm_session_permissions=True  # SSMセッションマネージャのアクセスを許可
        )

        # ALB用のセキュリティグループを作成
        alb_sg = ec2.SecurityGroup(
            self, 'FaceMatching-ALB-Sg',
            vpc=vpc,
            allow_all_outbound=True
        )

        # ALBを作成
        alb = elbv2.ApplicationLoadBalancer(
            self, 'FaceMatching-ALB',
            vpc=vpc,
            internet_facing=True,
            security_group=alb_sg
        )

        # ALBアクセスログ用バケットを作成
        log_bucket = s3.Bucket(self, "WEB-3sou-LogBucket")

        # ALBリスナーを作成
        http_listener = alb.add_listener('Listener', 
            port=80,
            open=True
        )

        # EC2インスタンスをターゲットに追加
        http_listener.add_targets("HttpTargets",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[targets.InstanceTarget(ec2_instance1, 80)],
            health_check=elbv2.HealthCheck(
                path="/"
            )
        )

        # ALBアクセスログ設定
        alb.log_access_logs(log_bucket)

        # ALB からインスタンスへのアクセスを許可
        alb.connections.allow_from(ec2_instance1, ec2.Port.tcp(80))

        cloudfront_distribution = cloudfront.Distribution(self, "FaceMatchingCloudFront",
            default_behavior={
                "origin": origins.LoadBalancerV2Origin(
                    alb,
                    protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,  # CloudFrontからALBへのリクエストはHTTPを使用
                ),
                "viewer_protocol_policy": cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,  # ビューアーからのリクエストはHTTPSにリダイレクト
                "allowed_methods": cloudfront.AllowedMethods.ALLOW_ALL,
                "cached_methods": cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                "cache_policy": cloudfront.CachePolicy.CACHING_DISABLED,  # キャッシュを無効に設定
                "origin_request_policy": cloudfront.OriginRequestPolicy.ALL_VIEWER,  # 全てのビューアー情報をオリジンに転送
                "compress": True,
            }
        )
        
app = App()
FaceMatchingStack(app, "FaceMatchingStack", env={
    'region': 'ap-northeast-1'  # 使用するリージョン
})
app.synth()
