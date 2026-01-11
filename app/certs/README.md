## Генерация ключей для JWT

1. Генерируем приватный ключ:
```bash
# Генерация приватного RSA ключа длины 2048
openssl genrsa -out jwt-private.pem 2048 
```

2. Генерируем публичный ключ на основе приватного:
```bash
# Выделяем публичный ключ из пары для сертификата
openssl rsa -in jwt-private.pem -outform PEM -pubout -out jwt-public.pem
```