# XFS-диск для данных MinIO

Свежие сборки MinIO AIStor (~с ноября 2026) отказываются форматировать
ext4-тома: диск «форматируется», но сервер так и не выходит в онлайн
(`drives-online: 0`), а все S3-запросы отвечают `403 AccessDenied`, хотя
`/minio/health` продолжает отвечать 200. Поэтому каталог из
`MINIO_DATA_DIR` (см. `backend/.env`) обязан лежать на XFS.

Ниже — разовая настройка на Linux-хосте: XFS-диск-петля (loop-image)
фиксированного размера, монтируемый через fstab. Команды рассчитаны на
Ubuntu/Debian и предполагают root-права (sudo).

## 1. Установка утилит

```bash
sudo apt-get update
sudo apt-get install -y xfsprogs
```

## 2. Создание и форматирование диска-петли

Размер подбирайте под ожидаемый объём документов; пример — 20 ГиБ.

```bash
sudo truncate -s 20G /srv/minio-dev.xfs
sudo mkfs.xfs -q /srv/minio-dev.xfs
sudo mkdir -p /srv/minio-data
```

`truncate` создаёт разреженный файл — реальное место расходуется только
по мере записи данных.

## 3. Монтирование через fstab

Добавьте строку в `/etc/fstab` (UID/GID не важны: каталог пишет
root-контейнер MinIO):

```
/srv/minio-dev.xfs  /srv/minio-data  xfs  loop  0  0
```

Смонтируйте:

```bash
sudo mount -a
```

## 4. Проверка

```bash
findmnt /srv/minio-data          # строка с fstype xfs
stat -f -c %T /srv/minio-data   # должно вывести: xfs
```

## 5. Подключение к compose

В `backend/.env`:

```bash
MINIO_DATA_DIR="/srv/minio-data"
```

Compose-скрипты (`infra/compose.yml`, `infra/deploy.sh`) берут путь из
этой переменной; запускать compose нужно с `--env-file backend/.env`,
поскольку в интерполяцию compose файлы секций `env_file` не попадают.
`docker compose down -v` затрагивает только именованные тома: ваш
XFS-каталог вы сами чистите вручную (`rm -rf` содержимого), при
необходимости начните с чистого `mkfs.xfs` заново.
