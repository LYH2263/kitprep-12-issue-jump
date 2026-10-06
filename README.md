# KitPrep 中央厨房 BOM 备料

按菜品 BOM 展开订单行、合并同原料需求，对照库存计算缺料并生成备料单。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:5000 |
| API | http://localhost:10100 |
| API 文档 | http://localhost:10100/docs |
| Postgres | localhost:5451 |

健康检查：`GET http://localhost:10100/api/health`

## 使用说明

1. 在「菜品」「BOM」维护中央厨房出品与用料树。
2. 在「订单」「库存」确认当日需求与现有库存。
3. 打开「备料单」展开合并原料需求；生成即按需求占用库存（占用↑，账面不动）。
4. 在「备料单」点「领料出库」：该单占用清零、账面按占用那一笔扣一次，单状态变为已领；重复领料会被拒绝，失败则状态/占用/账面全部退回。
5. 在「库存」页可直接按原料出库，与备料台领料同一扣账口径。
6. 在「缺料」查看 need − stock 为正的原料。

## 开发与测试

```bash
docker compose exec api pytest -q
```
