pipeline {
    agent any
    
    parameters {
        string(name: 'SOURCE_IP', description: 'Enter source IP address')
        string(name: 'DESTINATION_IP', description: 'Enter destination IP address')
        string(name: 'DESTINATION_PORT', description: 'Enter destination port')
    }
    
    environment {
        AWS_REGION = 'us-east-1'  // Change to your desired region
        LAMBDA_FUNCTION_NAME = 'network-connectivity-test'
    }
    
    stages {
        stage('Validate Input Parameters') {
            steps {
                script {
                    // Validate IP addresses format
                    def ipPattern = /^(\d{1,3}\.){3}\d{1,3}$/
                    
                    if (!(params.SOURCE_IP =~ ipPattern)) {
                        error "Invalid source IP format"
                    }
                    if (!(params.DESTINATION_IP =~ ipPattern)) {
                        error "Invalid destination IP format"
                    }
                    if (!(params.DESTINATION_PORT.isInteger() && params.DESTINATION_PORT.toInteger() in 1..65535)) {
                        error "Invalid port number"
                    }
                }
            }
        }
        
        stage('Determine VPC and Subnet') {
            steps {
                script {
                    // Find subnet that contains the source IP
                    def findSubnetCommand = """
                        aws ec2 describe-subnets \
                            --query 'Subnets[?contains(CidrBlock, \`${params.SOURCE_IP}\`)].{SubnetId:SubnetId,VpcId:VpcId}' \
                            --output json
                    """
                    def subnetInfo = readJSON text: sh(script: findSubnetCommand, returnStdout: true).trim()
                    
                    if (subnetInfo.size() == 0) {
                        error "No subnet found containing IP ${params.SOURCE_IP}"
                    }
                    
                    // Store subnet and VPC IDs
                    env.TARGET_SUBNET = subnetInfo[0].SubnetId
                    env.TARGET_VPC = subnetInfo[0].VpcId
                    
                    echo "Found Subnet: ${env.TARGET_SUBNET}"
                    echo "Found VPC: ${env.TARGET_VPC}"
                }
            }
        }
        
        stage('Create IAM Role') {
            steps {
                script {
                    // Create trust policy for Lambda
                    def trustPolicy = """
                    {
                        "Version": "2012-10-17",
                        "Statement": [{
                            "Effect": "Allow",
                            "Principal": {
                                "Service": "lambda.amazonaws.com"
                            },
                            "Action": "sts:AssumeRole"
                        }]
                    }
                    """
                    
                    // Create role policy for Lambda
                    def rolePolicy = """
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "ec2:CreateNetworkInterface",
                                    "ec2:DescribeNetworkInterfaces",
                                    "ec2:DeleteNetworkInterface",
                                    "ec2:AssignPrivateIpAddresses",
                                    "ec2:UnassignPrivateIpAddresses"
                                ],
                                "Resource": "*"
                            },
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents"
                                ],
                                "Resource": "arn:aws:logs:*:*:*"
                            }
                        ]
                    }
                    """
                    
                    // Write policies to files
                    writeFile file: 'trust-policy.json', text: trustPolicy
                    writeFile file: 'role-policy.json', text: rolePolicy
                    
                    // Create role and capture the role ARN
                    def createRoleCommand = """
                        aws iam create-role \
                            --role-name ${env.LAMBDA_FUNCTION_NAME}-role \
                            --assume-role-policy-document file://trust-policy.json \
                            --query 'Role.Arn' \
                            --output text || \
                        aws iam get-role \
                            --role-name ${env.LAMBDA_FUNCTION_NAME}-role \
                            --query 'Role.Arn' \
                            --output text
                    """
                    env.LAMBDA_ROLE_ARN = sh(script: createRoleCommand, returnStdout: true).trim()
                    
                    // Attach policy to role
                    sh """
                        aws iam put-role-policy \
                            --role-name ${env.LAMBDA_FUNCTION_NAME}-role \
                            --policy-name ${env.LAMBDA_FUNCTION_NAME}-policy \
                            --policy-document file://role-policy.json
                    """
                    
                    // Attach AWSLambdaBasicExecutionRole managed policy
                    sh """
                        aws iam attach-role-policy \
                            --role-name ${env.LAMBDA_FUNCTION_NAME}-role \
                            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
                    """
                    
                    // Wait for role to propagate
                    sleep 10
                }
            }
        }
        
        stage('Create Lambda Function') {
            steps {
                script {
                    // Create Python code for Lambda function
                    writeFile file: 'network_test.py', text: '''
import socket
import json

def lambda_handler(event, context):
    source_ip = event['source_ip']
    dest_ip = event['dest_ip']
    dest_port = int(event['dest_port'])
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((dest_ip, dest_port))
        sock.close()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': result == 0,
                'message': 'Port is open' if result == 0 else 'Port is closed'
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'message': str(e)
            })
        }
'''
                    
                    // Create ZIP file for Lambda deployment
                    sh 'zip network_test.zip network_test.py'
                    
                    // Create or update Lambda function with VPC configuration
                    sh """
                        aws lambda create-function \
                            --function-name ${env.LAMBDA_FUNCTION_NAME} \
                            --runtime python3.9 \
                            --handler network_test.lambda_handler \
                            --role ${env.LAMBDA_ROLE_ARN} \
                            --zip-file fileb://network_test.zip \
                            --vpc-config SubnetIds=${env.TARGET_SUBNET},SecurityGroupIds=${env.SECURITY_GROUP_ID} \
                        || aws lambda update-function-configuration \
                            --function-name ${env.LAMBDA_FUNCTION_NAME} \
                            --role ${env.LAMBDA_ROLE_ARN} \
                            --vpc-config SubnetIds=${env.TARGET_SUBNET},SecurityGroupIds=${env.SECURITY_GROUP_ID} \
                        && aws lambda update-function-code \
                            --function-name ${env.LAMBDA_FUNCTION_NAME} \
                            --zip-file fileb://network_test.zip
                    """
                }
            }
        }
        
        stage('Test Network Connectivity') {
            steps {
                script {
                    def payload = """
                        {
                            "source_ip": "${params.SOURCE_IP}",
                            "dest_ip": "${params.DESTINATION_IP}",
                            "dest_port": "${params.DESTINATION_PORT}"
                        }
                    """
                    
                    def invokeCommand = """
                        aws lambda invoke \
                            --function-name ${env.LAMBDA_FUNCTION_NAME} \
                            --payload '${payload}' \
                            response.json
                    """
                    
                    sh invokeCommand
                    
                    def response = readJSON file: 'response.json'
                    if (response.statusCode != 200) {
                        error "Network connectivity test failed: ${response.body.message}"
                    }
                    
                    echo "Network connectivity test result: ${response.body.message}"
                }
            }
        }
    }
    
    post {
        always {
            script {
                // Clean up Lambda function
                sh """
                    aws lambda delete-function --function-name ${env.LAMBDA_FUNCTION_NAME} || true
                """
                
                // Detach policies from role
                sh """
                    aws iam detach-role-policy \
                        --role-name ${env.LAMBDA_FUNCTION_NAME}-role \
                        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole || true
                    
                    aws iam delete-role-policy \
                        --role-name ${env.LAMBDA_FUNCTION_NAME}-role \
                        --policy-name ${env.LAMBDA_FUNCTION_NAME}-policy || true
                """
                
                // Delete the IAM role
                sh """
                    aws iam delete-role --role-name ${env.LAMBDA_FUNCTION_NAME}-role || true
                """
                
                cleanWs()
            }
        }
    }
}
