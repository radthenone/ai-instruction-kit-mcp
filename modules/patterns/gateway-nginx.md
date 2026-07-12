# Gateway Nginx — routing port-based

## Cel

Jeden gateway (Nginx) wystawia wiele portów — każdy port kieruje ruch do innej aplikacji Django. Lokalnie: `localhost:8010` → shop-app, `localhost:8020` → cars-app.

## Konfiguracja

```nginx
server {
    listen 8010;
    location / {
        proxy_pass http://shop-app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

server {
    listen 8020;
    location / {
        proxy_pass http://carwash-app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Docker Compose

- Gateway: `ports: ["8010:8010", "8020:8020"]`
- Serwisy aplikacji: `expose: ["8000"]` — **bez** publicznego `ports`
- Wszystkie serwisy w jednej sieci Docker

## Auth-service (wspólny)

Auth-service może być osobnym mikroserwisem dostępny wewnętrznie. Gateway routuje tylko aplikacje domenowe; auth może być pod `/auth/` na każdym porcie albo na osobnym entrypoincie — zależy od profilu projektu (overlay).

## Produkcja

Lokalnie port-based jest wygodny. Na produkcji preferuj subdomeny lub path-based na porcie 443 (TLS). Zmiana to tylko konfiguracja gateway — architektura serwisów zostaje.

## Frontend

React/Expo konfiguruje base URL per aplikacja:

- Shop: `http://localhost:8010`
- Cars: `http://localhost:8020`

Ten sam endpoint `/auth/login` — inny backend w zależności od portu.
