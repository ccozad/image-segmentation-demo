# Testing on a GPU EC2 instance

The worker needs an NVIDIA GPU, so the SAM 3 segmentation can't run on a machine
without one. If your development machine has no GPU, this is the quickest way to
exercise the **whole stack on a real GPU** without doing a full production
deploy.

It runs the normal dev stack — MinIO and all — on a single GPU instance and
reaches the UI over an SSH tunnel. **No domain, TLS, real S3, or code changes**
required; the only thing you set is `HF_TOKEN`. For a real public deployment
(S3 + HTTPS) use [`deploy.md`](./deploy.md) instead.

## 0. Request GPU quota first

New/low-usage AWS accounts default to **0 vCPUs** for G-type instances, which
blocks launching. In the console: **Service Quotas → Amazon EC2 → "Running
On-Demand G and VT instances"**. If it's `0`, request an increase to **≥ 4**
(enough for one `xlarge`). Approval can take minutes to a couple of days — do
this first.

## 1. Launch the instance

EC2 → Launch instance:

- **AMI:** search **"Deep Learning Base GPU AMI (Ubuntu 22.04)"**. It ships with
  the NVIDIA driver, Docker, and the NVIDIA Container Toolkit preinstalled,
  which skips the fiddly driver/toolkit setup.
- **Type:** `g4dn.xlarge` (T4 16 GB, ~$0.53/hr — cheapest, fine for SAM 3 image
  inference) or `g5.xlarge` (A10G 24 GB, ~$1/hr) for headroom.
- **Storage:** increase the root EBS volume to **~80 GB** (CUDA image + SAM 3
  checkpoint are several GB each).
- **Key pair:** create or pick one for SSH.
- **Security group:** allow **only SSH (22) from your IP**. The tunnel handles
  the rest — nothing else needs to be public.

> Prices change and bill **hourly even when idle** — confirm current rates and
> **stop/terminate when done** (step 5).

## 2. Verify the GPU reaches Docker

```sh
ssh -i your-key.pem ubuntu@<INSTANCE_PUBLIC_IP>

nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.6.2-base-ubuntu24.04 nvidia-smi
```

If the second command prints the GPU table, you're good. If it fails, the AMI
didn't include the toolkit — run the install commands in [`deploy.md`](./deploy.md)
§2, then retry.

## 3. Clone, set HF_TOKEN, launch

```sh
git clone https://github.com/ccozad/image-segmentation-demo.git
cd image-segmentation-demo
cp .env.example .env
nano .env            # set HF_TOKEN=hf_xxx ; leave S3_ENDPOINT etc. as-is (MinIO)

make up-gpu          # builds the CUDA worker + downloads the checkpoint (slow first time)
```

Watch the worker become ready:

```sh
docker compose logs -f segmentation_worker   # wait for "sam3.loaded" then "worker.ready"
```

(`make up-gpu` runs migrations automatically. If `make` is missing:
`sudo apt-get install -y make`.)

## 4. Open the UI through an SSH tunnel

From your **local machine** (any OS with an SSH client — a macOS/Linux terminal
or Windows PowerShell), forward both the frontend and API ports:

```sh
ssh -i your-key.pem -L 5173:localhost:5173 -L 8000:localhost:8000 ubuntu@<INSTANCE_PUBLIC_IP>
```

Then open **<http://localhost:5173>** in your browser. This works with no config
because the browser calls `localhost:8000` (tunneled to the instance's API), and
CORS already allows `localhost:5173`.

Upload an image with a prompt (e.g. `cars`) and watch it go
`pending → processing → done`. Try a prompt with no matches (e.g. `unicorns` on a
street scene) — it should come back `done` with `mask_count = 0` and the original
image.

## 5. Stop the instance when finished

It bills hourly even when idle.

```sh
# keep the disk, pay only for EBS:
aws ec2 stop-instances --instance-ids i-xxxxxxxx
# or stop all charges:
aws ec2 terminate-instances --instance-ids i-xxxxxxxx
```

(Or use **Instance state → Stop/Terminate** in the EC2 console.)

## Optional: bootstrap on first boot

To clone and pre-build during launch, paste this into **Advanced details → User
data** when launching (edit the token). It runs as root on first boot; the build
continues in the background after the instance is reachable.

```sh
#!/bin/bash
set -eux
cd /home/ubuntu
sudo -u ubuntu git clone https://github.com/ccozad/image-segmentation-demo.git
cd image-segmentation-demo
sudo -u ubuntu cp .env.example .env
echo 'HF_TOKEN=hf_xxxxxxxxxxxxxxxx' | sudo -u ubuntu tee -a .env
sudo -u ubuntu make up-gpu
```

> User data is stored in plaintext instance metadata — fine for a throwaway test
> token, but prefer setting `HF_TOKEN` over SSH (step 3) for anything you care
> about.

## Troubleshooting

- **Build fails / no `sam3.loaded`:** the worker image has unverified version
  pins (`SAM3_REF=main`, torch cu126 wheels, OpenCV 5). Capture
  `docker compose logs segmentation_worker` and the build output — those pins in
  `src/segmentation_worker/Dockerfile` / `worker/segmentation.py` are the likely
  fix points.
- **`could not select device driver "nvidia"`:** the NVIDIA Container Toolkit
  isn't active — see `deploy.md` §2.
- **Out of disk during build:** the root volume is too small; relaunch with ~80 GB.
