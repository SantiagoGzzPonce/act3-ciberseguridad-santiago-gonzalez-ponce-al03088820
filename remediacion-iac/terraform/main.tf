# ---------------------------------------------------------------------------
# Red: VPC y subred para la "instancia EC2" que representa el escenario
# ---------------------------------------------------------------------------
resource "aws_vpc" "app" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = "act3-vpc" }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.app.id
  cidr_block              = "10.20.1.0/24"
  map_public_ip_on_launch = false
  tags                    = { Name = "act3-public" }
}

# ---------------------------------------------------------------------------
# Paso 6.1: grupo de seguridad con mínimo de puertos
#   - 443 abierto (HTTPS público)
#   - 22 solo desde la IP del administrador
#   - 8000 (gunicorn), 4566, 2375/2376 (Docker API), 5001 NO se exponen
# ---------------------------------------------------------------------------
resource "aws_security_group" "web" {
  name        = "act3-web-sg"
  description = "Solo HTTPS publico y SSH restringido"
  vpc_id      = aws_vpc.app.id
  tags        = { Name = "act3-web-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  security_group_id = aws_security_group.web.id
  description       = "HTTPS publico"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "ssh_admin" {
  security_group_id = aws_security_group.web.id
  description       = "SSH solo administrador"
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = var.admin_cidr
}

resource "aws_vpc_security_group_egress_rule" "https_out" {
  security_group_id = aws_security_group.web.id
  description       = "Salida HTTPS (actualizaciones, APIs)"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

# ---------------------------------------------------------------------------
# IAM de menor privilegio: la instancia solo puede leer/escribir SU bucket
# (nada de AdministratorAccess ni "Action": "*")
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "assume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app" {
  name               = "act3-app-role"
  assume_role_policy = data.aws_iam_policy_document.assume_ec2.json
}

data "aws_iam_policy_document" "app_s3" {
  statement {
    sid       = "ListOnlyAppBucket"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.bucket_name}"]
  }
  statement {
    sid       = "RWObjectsOnlyAppBucket"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["arn:aws:s3:::${var.bucket_name}/*"]
  }
}

resource "aws_iam_policy" "app_s3" {
  name   = "act3-app-s3-minimo"
  policy = data.aws_iam_policy_document.app_s3.json
}

resource "aws_iam_role_policy_attachment" "app_s3" {
  role       = aws_iam_role.app.name
  policy_arn = aws_iam_policy.app_s3.arn
}

resource "aws_iam_instance_profile" "app" {
  name = "act3-app-profile"
  role = aws_iam_role.app.name
}

# ---------------------------------------------------------------------------
# Instancia (IaaS): disco cifrado, IMDSv2 obligatorio, sin IP pública directa
# ---------------------------------------------------------------------------
resource "aws_instance" "app" {
  ami                         = var.ami_id
  instance_type               = "t3.micro"
  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.web.id]
  iam_instance_profile        = aws_iam_instance_profile.app.name
  associate_public_ip_address = false

  metadata_options {
    http_tokens                 = "required" # IMDSv2: mitiga robo de credenciales vía SSRF
    http_put_response_hop_limit = 1          # contenedores no alcanzan el IMDS
  }

  root_block_device {
    encrypted = true
  }

  tags = { Name = "act3-mfa-app" }
}

output "security_group_id" {
  value = aws_security_group.web.id
}

output "puertos_expuestos" {
  value = ["443/tcp (0.0.0.0/0)", "22/tcp (${var.admin_cidr})"]
}
