# otchet_main — отчёт и его скриншоты

Здесь лежит итоговый Word-отчёт и все скриншоты, которые в него встроены.

```
otchet_main/
├─ ОТЧЁТ_Milvus_банковские_данные.docx   # сам отчёт (43 рисунка, 25 таблиц, 47 формул)
└─ screens/                               # 24 скриншота Attu, встроенных в отчёт
   ├─ S00_login.png … S25_anomaly_lowsim.png
```

## Что где используется

| Раздел отчёта | Скриншоты |
|---|---|
| 2.1, 3.1 | `S01_cluster_overview.png`, `S00_login.png` |
| 2.3 / 2.3.1–2.3.6 | `S02_collections.png`, `S03_schema_products.png`, `S14_schema_clients.png`, `S17_schema_currencies.png`, `S18_schema_accounts.png`, `S19_schema_cards.png`, `S13_schema_transactions.png` |
| 2.4 | `S15_index_products.png`, `S20_index_transactions.png` |
| 2.7 / 3.5.1 | `S06_users.png`, `S07_roles.png`, `S21_role_privileges.png` |
| 2.8 / 3.5.3 | `S24_resource_groups.png` |
| 2.9.1 / 3.4.1 | `S05_search_products.png` |
| 3.3 | `S04_data_products.png`, `S09_embedding_e5_test.png`, `S10_embedding_providers.png` |
| 3.4.2 | `S16_search_transactions.png` |
| 3.4.3 | `S25_anomaly_lowsim.png`, `S22_search_tx_anomalies.png` |
| 3.5.2 | `S23_rbac_verification.png` |
| 3.6 | `S08_metrics.png` |

## Как пересобрать отчёт

Из корня репозитория:

```powershell
python tools\make_report.py
```

Сборщик читает исходник `report/otchet_v3.txt` (это отчёт с переписанным под наш
репозиторий разделом 3.1), вставляет доказательства шагов (команды, вывод консоли из
`report/evidence/*.txt`, скриншоты из `otchet_main/screens/`) и пересобирает .docx
через OfficeCLI.

Скрипты-шаги, которыми получены подтверждения главы 3, лежат в `report/steps/`.

> Скриншоты для стенда Milvus 2.6.11 (не входят в этот отчёт) — в `../screens/report26/`.
