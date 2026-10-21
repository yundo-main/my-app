# my-app

CI/CD 전체 흐름은 [실습 시나리오의 흐름도](../CI-CD-SCENARIO.md)를 참고하세요.

FastAPI 애플리케이션을 컨테이너 이미지로 빌드하기 위한 디렉터리입니다.

## 디렉터리 구성

```text
my-app/
├── Dockerfile
├── requirements.txt
├── main.py
├── tests/
│   └── test_main.py
├── .github/
│   └── workflows/
│       └── ci.yml
└── README.md
```

`Dockerfile`은 다음 파일을 실행하도록 구성되어 있습니다.

```text
main:app
```

`main.py`에 `app = FastAPI()` 객체가 있어야 합니다.

## 의존성 사전 준비

실습 중 의존성 오류가 발생하지 않도록 실행 및 테스트 패키지를 미리 설치합니다.

```bash
cd devops/my-app
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q
```

`requirements.txt` 하나에 컨테이너 실행 패키지와 테스트 패키지를 모두 관리합니다.
GitHub Actions도 동일한 파일을 사용하므로 로컬과 CI의 의존성 구성이 일치합니다.

## Dockerfile 설명

```dockerfile
FROM python:3.9-slim
```

Python 3.9 기반의 경량 이미지를 사용합니다. `python:3.9-slim`은
amd64와 arm64 플랫폼을 지원하므로 멀티플랫폼 빌드에 사용할 수 있습니다.

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

Python 의존성을 `requirements.txt`에서 설치합니다.

```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

컨테이너가 시작되면 FastAPI를 8000번 포트로 실행합니다.

## 멀티플랫폼 이미지 빌드

멀티플랫폼 이미지는 Dockerfile에 플랫폼을 고정하지 않고
`docker buildx build` 명령의 `--platform` 옵션으로 생성합니다.

### 1. Buildx 확인

```bash
docker buildx version
```

Buildx 빌더가 없으면 생성합니다.

```bash
docker buildx create \
  --name multiarch-builder \
  --driver docker-container \
  --use

docker buildx inspect --bootstrap
```

이미 생성된 빌더를 사용하는 경우:

```bash
docker buildx use multiarch-builder
```

### 2. ECR 로그인

```bash
aws ecr get-login-password \
  --region ap-northeast-2 | \
docker login \
  --username AWS \
  --password-stdin 637423638906.dkr.ecr.ap-northeast-2.amazonaws.com
```

### 3. ECR 이미지 빌드 및 Push

프로젝트 루트에서 실행합니다.

```bash
cd devops/my-app

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t 637423638906.dkr.ecr.ap-northeast-2.amazonaws.com/fastapi-backend:v1.0 \
  -t 637423638906.dkr.ecr.ap-northeast-2.amazonaws.com/fastapi-backend:latest \
  --push \
  .
```

플랫폼별 이미지를 하나의 manifest 목록으로 ECR에 업로드합니다.

- `linux/amd64`: 일반 x86 EKS 노드
- `linux/arm64`: AWS Graviton ARM 노드
- `--push`: 멀티플랫폼 이미지를 ECR에 업로드
- `--load`: 단일 플랫폼 로컬 이미지에 사용

멀티플랫폼 빌드에서는 `--load` 대신 반드시 `--push`를 사용합니다.

## 이미지 플랫폼 확인

```bash
docker buildx imagetools inspect \
  637423638906.dkr.ecr.ap-northeast-2.amazonaws.com/fastapi-backend:v1.0
```

다음 플랫폼이 표시되어야 합니다.

```text
linux/amd64
linux/arm64
```

ECR 태그 목록 확인:

```bash
aws ecr describe-images \
  --region ap-northeast-2 \
  --repository-name fastapi-backend \
  --query 'imageDetails[].imageTags' \
  --output table
```

## Dockerfile 플랫폼 설정 주의사항

다음처럼 Dockerfile에서 플랫폼을 고정하지 않습니다.

```dockerfile
FROM --platform=linux/amd64 python:3.9-slim
```

플랫폼을 고정하면 arm64 이미지를 제대로 생성할 수 없습니다.

다음처럼 기본 이미지만 지정합니다.

```dockerfile
FROM python:3.9-slim
```

## Kubernetes에서 사용

Deployment의 이미지를 ECR 이미지로 지정합니다.

```yaml
containers:
  - name: backend
    image: 637423638906.dkr.ecr.ap-northeast-2.amazonaws.com/fastapi-backend:v1.0
```

Kubernetes가 노드의 아키텍처에 맞는 이미지를 자동으로 선택합니다.

노드 아키텍처 확인:

```bash
kubectl get nodes -L kubernetes.io/arch
```

Pod가 사용하는 이미지 확인:

```bash
kubectl get pods -A \
  -o custom-columns='NAMESPACE:.metadata.namespace,POD:.metadata.name,IMAGE:.spec.containers[*].image'
```

## CI/CD 설정

`.github/workflows/ci.yml`은 `main` Push마다 테스트 → 멀티플랫폼 이미지 빌드 →
ECR Push(Commit SHA 태그) → `my-k8s-manifests`의 이미지 태그 갱신을 수행합니다.
Argo CD가 그 변경을 감지해 EKS에 배포합니다.

이 저장소에서 직접 필요한 설정은 GitHub Secret 2개입니다.

| Secret | 용도 |
|---|---|
| `AWS_GITHUB_ACTIONS_ROLE_ARN` | GitHub OIDC로 AWS IAM Role을 받아 ECR에 접근 (장기 Access Key 미사용) |
| `MANIFEST_REPO_TOKEN` | `my-k8s-manifests`에 이미지 태그 변경을 Commit·Push |

발급·등록 절차(OIDC Provider, Role 신뢰 정책의 `sub`, PAT/Deploy Key)와 CI 실패
메시지별 원인은 시나리오 문서가 단일 출처입니다. 이 README에서는 중복해서
설명하지 않습니다.

- [GitHub Actions AWS 인증과 Secret 등록 (1.5)](../CI-CD-SCENARIO.md#15-github-actions-aws-인증-설정-확인)
- [CI/CD 변경 실습과 CI 실패 시 읽는 법 (2.7)](../CI-CD-SCENARIO.md#27-cicd-변경-실습)
- [Ingress-NGINX·Argo CD 설치 (2.4)](../CI-CD-SCENARIO.md#24-ingress-nginxargo-cd-설치)
- [Monolith 배포·Application 등록 (2.5)](../CI-CD-SCENARIO.md#25-monolith-배포)
- [Argo CD GUI 확인 (2.6)](../CI-CD-SCENARIO.md#argo-cd-gui로-배포-상태-확인)

현재 상태를 빠르게 확인하는 명령은 다음과 같습니다.

```bash
gh secret list --repo yundo-main/my-app
gh run list --repo yundo-main/my-app --limit 3
```

## 단일 플랫폼 로컬 테스트

멀티플랫폼 이미지는 `--load`로 로컬 Docker에 적재할 수 없으므로,
플랫폼별로 따로 테스트합니다.

```bash
docker buildx build \
  --platform linux/amd64 \
  -t fastapi-backend:test-amd64 \
  --load \
  .
```

```bash
docker run --rm -p 8000:8000 fastapi-backend:test-amd64
```

## 주의사항

- `main.py`가 없으면 이미지 빌드는 되더라도 컨테이너 실행에 실패합니다.
- `secret.yml`은 실습용 평문 Secret이므로 공개 저장소에 업로드하지 않습니다.
- 운영 환경에서는 AWS Secrets Manager 또는 External Secrets를 사용합니다.
- `latest`보다 `v1.0`, Git SHA 같은 고정 태그 사용을 권장합니다.
