#!/usr/bin/env bash
# Fase C: comprobaciones con AWS CLI contra LocalStack (nunca AWS real).
set -u
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1
EP="--endpoint-url http://localhost:4566"
B=actividad3-seguro-local

echo "== Salud de LocalStack";        curl -s http://localhost:4566/_localstack/health; echo
echo "== Buckets";                    aws $EP s3api list-buckets
echo "== Cifrado";                    aws $EP s3api get-bucket-encryption --bucket $B
echo "== Bloqueo de acceso público";  aws $EP s3api get-public-access-block --bucket $B
echo "== Subir archivo de prueba"
echo "archivo de prueba act3 $(date -Is)" > prueba.txt
aws $EP s3 cp prueba.txt s3://$B/prueba.txt
aws $EP s3 ls s3://$B/
echo "== Descarga ANÓNIMA (sin firmar)"
aws $EP s3 cp s3://$B/prueba.txt descarga-anonima.txt --no-sign-request \
  && echo "RESULTADO: permitido (limitación del simulador, ver reporte)" \
  || echo "RESULTADO: denegado"
echo "== Política del bucket"
aws $EP s3api get-bucket-policy-status --bucket $B || echo "(NoSuchBucketPolicy = no hay política; no implica exposición pública)"
