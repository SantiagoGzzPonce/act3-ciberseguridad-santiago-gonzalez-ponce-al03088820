variable "admin_cidr" {
  description = "IP pública del administrador (/32). Único origen permitido para SSH."
  type        = string
  default     = "203.0.113.10/32" # TEST-NET-3 (RFC 5737): reemplazar por tu IP

  validation {
    condition     = var.admin_cidr != "0.0.0.0/0" && endswith(var.admin_cidr, "/32")
    error_message = "SSH nunca debe abrirse a 0.0.0.0/0; usa una sola IP /32."
  }
}

variable "bucket_name" {
  type    = string
  default = "actividad3-seguro-local"
}

variable "ami_id" {
  type    = string
  default = "ami-df5de72bdb3b" # AMI simulada de LocalStack
}
