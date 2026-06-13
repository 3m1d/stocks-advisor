# Cron train service (LSTM + GPU)

Отдельный cron-контейнер для переобучения LSTM. Требует NVIDIA GPU и [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) на хосте.


Расписание: `docker/cron-train/crontab`.

## Запуск

```bash
make docker-up-prod
make docker-build-cron-train-prod   # только этот образ
```

## GPU

Compose пробрасывает GPU через `gpus: all`. Проверка внутри контейнера:

```bash
docker exec stocks-advisor-cron-train uv run python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu')"
```

## Логи

```bash
docker compose -f docker-compose-production.yml --env-file production.env logs -f cron-train
docker exec stocks-advisor-cron-train tail -f /var/log/cron/lstm_retrain.log
```

## Ручной запуск

```bash
docker exec stocks-advisor-cron-train /app/docker/cron-train/run-lstm-retrain.sh
```
