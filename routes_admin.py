from fastapi import APIRouter

router = APIRouter(prefix='/api/admin', tags=['admin'])


@router.get('/health')
def admin_health() -> dict[str, str]:
    return {'status': 'ok'}
