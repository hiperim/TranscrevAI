# PowerShell script to build Multi-Architecture Docker image (AMD64 + ARM64)
# Supports Intel/AMD CPUs and Apple Silicon
# Pushes to Docker Hub with platform manifests

$ErrorActionPreference = 'Stop'

Write-Host ""
Write-Host "Building TranscrevAI Multi-Architecture Docker Image"
Write-Host "   Platforms: linux/amd64, linux/arm64"
Write-Host "   Embedded ML Models with offline support"
Write-Host ""

# Load environment variables from .env
if (Test-Path ".env") {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^(?<name>.*?)=(?<value>.*)$') {
            $name = $Matches['name'].Trim()
            $value = $Matches['value'].Trim().Trim('"').Trim("'")
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
    Write-Host ".env loaded"
} else {
    Write-Host "Warning: .env not found"
}

# Step 1: Remove existing builder and create fresh one with DNS config
Write-Host ""
Write-Host "Setting up buildx builder..."

docker buildx rm multiarch-fixed --force 2>$null
docker buildx create --name multiarch-fixed --driver docker-container --buildkitd-config "$PSScriptRoot\..\buildkitd.toml" --use
docker buildx inspect --bootstrap

Write-Host "Builder ready"

# Step 2: Get Docker Hub username and tag
Write-Host ""
$dockerUsername = Read-Host "Enter Docker Hub username [hiperim]"
if ([string]::IsNullOrEmpty($dockerUsername)) { $dockerUsername = "hiperim" }

$imageTag = Read-Host "Enter image tag [latest]"
if ([string]::IsNullOrEmpty($imageTag)) { $imageTag = "latest" }

$imageName = "$dockerUsername/transcrevai:$imageTag"

Write-Host ""
Write-Host "Building: $imageName"
Write-Host "   Platforms: linux/amd64, linux/arm64"
Write-Host "   No cache (clean build)"
Write-Host ""

# Step 3: Build and push
docker buildx build `
    --platform linux/amd64,linux/arm64 `
    --no-cache `
    --file Dockerfile.multiarch `
    --tag $imageName `
    --push `
    .

Write-Host ""
Write-Host "Build and push complete: $imageName"
Write-Host "   linux/amd64 (Intel/AMD servers)"
Write-Host "   linux/arm64 (Apple Silicon)"
Write-Host ""
Write-Host "To run on server:"
Write-Host "  docker compose -f docker-compose.pull.yml up -d --pull always"
