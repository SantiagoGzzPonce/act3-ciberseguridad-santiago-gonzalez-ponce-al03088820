variable "bucket_name" {
  type    = string
  default = "actividad3-seguro-local"
}

# 1) Bucket
resource "aws_s3_bucket" "seguro" {
  bucket        = var.bucket_name
  force_destroy = true
  tags = {
    Proyecto = "act3-ciberseguridad"
    Entorno  = "localstack"
  }
}

# 2) Cifrado en reposo SSE-S3 (AES-256)
resource "aws_s3_bucket_server_side_encryption_configuration" "seguro" {
  bucket = aws_s3_bucket.seguro.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 3) Los cuatro controles de bloqueo de acceso público
resource "aws_s3_bucket_public_access_block" "seguro" {
  bucket                  = aws_s3_bucket.seguro.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

output "bucket" {
  value = aws_s3_bucket.seguro.bucket
}
