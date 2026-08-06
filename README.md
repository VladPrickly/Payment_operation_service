# Описание
API - сервис, который проводит платёжную операцию через внешнего провайдера и сохраняет корректное состояние при повторах, 
конкурентных запросах, потерянных HTTP-ответах и перезапусках.
Внешнюю систему изображает готовый provider-simulator. Сервис должен действительно вызывать его по HTTP. 
Успешный транспортный ответ не доказывает завершение платежа, а отсутствие ответа не доказывает, что платёж не был создан. 
Финальный результат определяется только callback-квитанцией.

Сервис содержит следующие эндпоинты:

- GET	/health	200	Проверка готовности
- POST	/operations	201	Создание операции
- POST	/operations/{id}/submit	202 или 200	Надёжно запланировать отправку
- POST	/receipts	204	Принять callback-квитанцию
- GET	/operations/{id}	200	Получить текущее состояние
- GET	/operations/{id}/events	200	Получить историю переходов


## Предварительные требования
- Python 3.12+
- Git
- Docker и Docker Compose
- Доступ к интернету

## Структура проекта
  ```
 payment_operation_service
  ├── app/
  │   ├── __init__.py
  │   ├── config.py
  │   ├── db.py
  │   ├── lifespan.py
  │   ├── main.py
  │   ├── provider.py  
  │   └── models.py
  ├── README.md
  ├── .env
  ├── .env.example
  ├── .gitignore
  ├── .dockerignore
  ├── requirements.txt
  ├── Dockerfile
  └── docker-compose.yml

  ```

## Переменные окружения (файл .env) по примеру .env.example
  ```
POSTGRES_USER=app_user
POSTGRES_PASSWORD=app_password
POSTGRES_DB=payment_db

DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}

PROVIDER_URL=http://provider-simulator:8081
CALLBACK_URL=http://candidate-service:8080/receipts

  ```

## Локальная установка 
1. Создайте виртуальное окружение:
- Windows:
  ```
  python -m venv .venv
  ```
- Linux/macOS:
  ```
  python3 -m venv .venv
  ```

2. Активируйте виртуальное окружение:
- Windows:
  ```
  .venv\Scripts\activate
  ```
- Linux/macOS:
  ```
  source .venv/bin/activate
  ```

3. Установите зависимости
  ```
  pip install -r requirements.txt
  ```

4. Запустите приложение
  ```
  uvicorn app.main:app --reload --port 8080
  ```
## Запуск приложения и создание БД
  ```
  docker-compose build
  docker-compose up
  
  Приложение запустится локально на http://127.0.0.1:8080/. БД будет создана при первом запуске.
  ```

## Остановка приложения:
  ```
  docker-compose down
  ```

## Удаление контейнеров и томов:
  ```
  docker-compose down -v
  ```

## Проверка работы
  ```
  ### Проверка готовности
  curl http://localhost:8080/health
  ```
  ```
  ### Создание операции
  curl -X POST http://localhost:8080/operations \
  -H "Content-Type: application/json" \
  -d '{"operationId": "op-123", "amount": "1000.00", "currency": "RUB", "description": "Test"}'
  ```

  ```
  ### Попытка повторного создания
  curl -X POST http://localhost:8080/operations \
    -H "Content-Type: application/json" \
    -d '{"operationId": "op-123", "amount": "1000.00", "currency": "RUB", "description": "Test"}'
  ```

  ```
  ### Отправка операции провайдеру
  curl -X POST http://localhost:8080/operations/op-123/submit
  ```

  ```
  ### Проверка состояния
  curl http://localhost:8080/operations/op-123
  ```

  ```
  ### Просмотр истории событий
  curl http://localhost:8080/operations/op-123/events
  ```

  ```
  ### Имитация прихода квитанции
  curl -X POST http://localhost:8080/receipts \
    -H "Content-Type: application/json" \
    -d '{"providerPaymentId": "test-provider-id", "operationId": "op-123", "result": "COMPLETED", "message": "Success", "occurredAt": "2026-08-04T12:00:00Z"}'
 ```

 ```
  ### Финальная проверка
  curl http://localhost:8080/operations/op-123
 
  ```


## Автор
- Владислав
- telegram: @vlad_705
- [e-mail](vlad.prickly@gmail.com)
- [github.com](https://github.com/VladPrickly)