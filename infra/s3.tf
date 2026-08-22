resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "raw_data" {
  bucket        = "${var.project_name}-raw-${random_id.bucket_suffix.hex}"
  force_destroy = true
}

resource "aws_s3_bucket" "analysis_results" {
  bucket        = "${var.project_name}-results-${random_id.bucket_suffix.hex}"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "raw_data" {
  bucket = aws_s3_bucket.raw_data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "analysis_results" {
  bucket = aws_s3_bucket.analysis_results.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_object" "sample_sales" {
  bucket = aws_s3_bucket.raw_data.id
  key    = "sample_sales.csv"
  source = "${path.module}/../data/sample_sales.csv"

  etag = filemd5("${path.module}/../data/sample_sales.csv")
}