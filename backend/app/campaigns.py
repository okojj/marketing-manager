from datetime import datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ConfigDict, Field, model_validator
from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError, IntegrityError
from sqlalchemy.orm import Session
from app.ai import Channel, StrictModel, AIError, get_provider, active_model, provider_configured
from app.auth import current_user, require_origin
from app.brands import owned_brand
from app.config import settings
from app.db import get_db
from app.models import Brand, User, Generation, Campaign, Content, ContentRevision

router = APIRouter(prefix='/api', tags=['campaigns'])
write = [Depends(require_origin)]

class Brief(StrictModel):
    topic: str = Field(min_length=1, max_length=500)
    keywords: str = Field(default='', max_length=500)
    goal: str = Field(min_length=1, max_length=500)
    direction: str = Field(default='', max_length=2000)
    channels: list[Channel] = Field(min_length=1, max_length=3)

    @model_validator(mode='after')
    def unique_channels(self):
        if len(set(self.channels)) != len(self.channels): raise ValueError('채널은 중복 선택할 수 없습니다.')
        return self

class IdeasInput(Brief):
    request_key: UUID

class CampaignInput(Brief):
    title: str = Field(min_length=1, max_length=200)
    source_generation_id: int | None = None
    idea_index: int | None = Field(default=None, ge=0, le=2)

class GenerateInput(StrictModel):
    request_key: UUID

class ContentInput(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=12000)
    revision: int = Field(ge=1)

class ContentOutput(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    channel: str
    title: str
    body: str
    revision: int

class RevisionOutput(StrictModel):
    model_config = ConfigDict(from_attributes=True)
    revision: int
    title: str
    body: str
    source: str
    created_at: datetime


def snapshot(brand: Brand) -> dict:
    return {k:getattr(brand,k) for k in ('name','description','target_audience','tone')}

def campaign_owned(campaign_id: int, db: Session, user: User) -> Campaign:
    campaign = db.scalar(select(Campaign).join(Brand).where(Campaign.id==campaign_id, Brand.owner_id==user.id))
    if campaign is None: raise HTTPException(404,'캠페인을 찾을 수 없습니다.')
    return campaign

def campaign_json(campaign: Campaign, db: Session) -> dict:
    contents = db.scalars(select(Content).where(Content.campaign_id==campaign.id).order_by(Content.id)).all()
    return {k:getattr(campaign,k) for k in ('id','brand_id','title','goal','brief','keywords','channels','brand_snapshot','created_at')} | {
        'contents':[ContentOutput.model_validate(c).model_dump() for c in contents]}

def generation_json(g: Generation) -> dict:
    return {'id':g.id,'request_key':g.request_key,'input':g.input_data,'result':g.result,
            'error':g.error,'created_at':g.created_at}

def lock_generation_user(db: Session, user: User):
    # MVP: one synchronous generation at a time per user, across all API replicas.
    # NOWAIT avoids queuing duplicate paid requests behind a long model call.
    user_id = user.id
    # End the auth/read snapshot before locking so MySQL REPEATABLE READ sees the
    # preceding generation's committed result when handling a retry.
    db.rollback()
    try:
        db.execute(select(User.id).where(User.id==user_id).with_for_update(nowait=True)).scalar_one()
    except OperationalError as exc:
        db.rollback()
        raise HTTPException(409,'이미 콘텐츠를 생성하고 있습니다. 완료 후 다시 시도해 주세요.') from exc

def generate(db: Session, user: User, brand_id: int, key: UUID, kind: str, context: dict) -> Generation:
    existing = db.scalar(select(Generation).where(Generation.owner_id==user.id, Generation.request_key==str(key)))
    if existing:
        if existing.kind != kind or existing.brand_id != brand_id or existing.input_data != context:
            raise HTTPException(409,'동일한 요청 식별자로 다른 내용을 생성할 수 없습니다.')
        if existing.error: raise HTTPException(502,existing.error)
        return existing
    count = db.scalar(select(func.count()).select_from(Generation).where(
        Generation.owner_id==user.id, Generation.created_at>=datetime.utcnow()-timedelta(days=1)))
    if count >= settings.ai_daily_limit: raise HTTPException(429,'최근 24시간의 AI 생성 한도에 도달했습니다.')
    try:
        provider = get_provider()
    except AIError as exc: raise HTTPException(exc.status,str(exc)) from exc
    generation = Generation(owner_id=user.id,brand_id=brand_id,request_key=str(key),kind=kind,
        input_data=context,provider=settings.ai_provider,model=active_model())
    db.add(generation)
    try:
        result, usage = provider.generate(kind,context)
    except AIError as exc:
        generation.error = str(exc)
        db.commit()  # Failed attempts also count towards the rolling usage limit.
        raise HTTPException(exc.status,str(exc)) from exc
    generation.result = result
    generation.usage = usage
    db.flush()
    return generation

@router.get('/ai/config')
def ai_config(user: User = Depends(current_user)):
    return {'enabled':provider_configured(),'provider':settings.ai_provider,
            'model':active_model(), 'daily_limit':settings.ai_daily_limit}

@router.get('/brands/{brand_id}/ideas')
def idea_history(brand_id: int, db: Session=Depends(get_db), user: User=Depends(current_user)):
    owned_brand(brand_id,db,user)
    return [generation_json(g) for g in db.scalars(select(Generation).where(
        Generation.brand_id==brand_id,Generation.owner_id==user.id,Generation.kind=='ideas')
        .order_by(Generation.id.desc()).limit(50))]

@router.post('/brands/{brand_id}/ideas', dependencies=write)
def ideas(brand_id: int, data: IdeasInput, db: Session=Depends(get_db), user: User=Depends(current_user)):
    brand = owned_brand(brand_id,db,user)
    lock_generation_user(db,user)
    context = {'brand':snapshot(brand),**data.model_dump(exclude={'request_key'})}
    result = generate(db,user,brand_id,data.request_key,'ideas',context)
    db.commit()
    return generation_json(result)

@router.get('/brands/{brand_id}/campaigns')
def campaigns(brand_id: int, db: Session=Depends(get_db), user: User=Depends(current_user)):
    owned_brand(brand_id,db,user)
    return [campaign_json(c,db) for c in db.scalars(select(Campaign).where(Campaign.brand_id==brand_id).order_by(Campaign.id.desc()))]

@router.post('/brands/{brand_id}/campaigns', dependencies=write, status_code=201)
def create_campaign(brand_id: int, data: CampaignInput, db: Session=Depends(get_db), user: User=Depends(current_user)):
    brand = owned_brand(brand_id,db,user)
    if (data.source_generation_id is None) != (data.idea_index is None):
        raise HTTPException(422,'아이디어와 생성 이력을 함께 지정해 주세요.')
    if data.source_generation_id is not None:
        source = db.scalar(select(Generation).where(Generation.id==data.source_generation_id,
            Generation.brand_id==brand_id,Generation.owner_id==user.id,Generation.kind=='ideas'))
        if not source or not source.result or source.error: raise HTTPException(404,'아이디어를 찾을 수 없습니다.')
        if data.idea_index >= len(source.result['ideas']): raise HTTPException(422,'아이디어 번호를 확인해 주세요.')
        existing = db.scalar(select(Campaign).where(Campaign.source_generation_id==source.id,Campaign.idea_index==data.idea_index))
        if existing: return campaign_json(existing,db)
    campaign = Campaign(brand_id=brand_id,title=data.title,goal=data.goal,
        brief=data.topic+'\n'+data.direction,keywords=data.keywords,channels=data.channels,
        brand_snapshot=snapshot(brand),source_generation_id=data.source_generation_id,idea_index=data.idea_index)
    db.add(campaign)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        if data.source_generation_id is None: raise
        existing = db.scalar(select(Campaign).where(Campaign.source_generation_id==data.source_generation_id,Campaign.idea_index==data.idea_index))
        if not existing: raise
        return campaign_json(existing,db)
    return campaign_json(campaign,db)

@router.get('/campaigns/{campaign_id}')
def get_campaign(campaign_id: int, db: Session=Depends(get_db), user: User=Depends(current_user)):
    return campaign_json(campaign_owned(campaign_id,db,user),db)

@router.post('/campaigns/{campaign_id}/generate', dependencies=write)
def generate_drafts(campaign_id: int, data: GenerateInput, db: Session=Depends(get_db), user: User=Depends(current_user)):
    campaign = campaign_owned(campaign_id,db,user)
    lock_generation_user(db,user)
    # Never overwrite existing or manually edited drafts on retries/double clicks.
    existing = db.scalar(select(Content.id).where(Content.campaign_id==campaign_id).with_for_update())
    if existing: return campaign_json(campaign,db)
    context = {'campaign_id':campaign_id,'brand':campaign.brand_snapshot,'title':campaign.title,
        'goal':campaign.goal,'brief':campaign.brief,'keywords':campaign.keywords,'channels':campaign.channels}
    result = generate(db,user,campaign.brand_id,data.request_key,'drafts',context)
    for draft in result.result['contents']:
        content = Content(campaign_id=campaign.id,**draft,revision=1)
        db.add(content);db.flush()
        db.add(ContentRevision(content_id=content.id,revision=1,title=content.title,body=content.body,source='ai'))
    db.commit()
    return campaign_json(campaign,db)

@router.put('/contents/{content_id}', dependencies=write, response_model=ContentOutput)
def edit_content(content_id: int, data: ContentInput, db: Session=Depends(get_db), user: User=Depends(current_user)):
    content = db.scalar(select(Content).join(Campaign).join(Brand).where(Content.id==content_id,Brand.owner_id==user.id).with_for_update())
    if not content: raise HTTPException(404,'콘텐츠를 찾을 수 없습니다.')
    if content.revision != data.revision: raise HTTPException(409,'다른 화면에서 수정되었습니다. 최신 내용을 다시 불러와 주세요.')
    limit = {'blog':12000,'instagram':2200,'linkedin':3000}[content.channel]
    if len(data.body)>limit: raise HTTPException(422,f'이 채널의 본문은 {limit}자 이내로 작성해 주세요.')
    if content.title == data.title and content.body == data.body: return content
    content.title, content.body = data.title, data.body
    content.revision += 1
    db.add(ContentRevision(content_id=content.id,revision=content.revision,title=content.title,body=content.body,source='manual'))
    db.commit(); db.refresh(content)
    return content

@router.get('/contents/{content_id}/revisions', response_model=list[RevisionOutput])
def revisions(content_id: int, db: Session=Depends(get_db), user: User=Depends(current_user)):
    content = db.scalar(select(Content).join(Campaign).join(Brand).where(Content.id==content_id,Brand.owner_id==user.id))
    if not content: raise HTTPException(404,'콘텐츠를 찾을 수 없습니다.')
    return db.scalars(select(ContentRevision).where(ContentRevision.content_id==content_id).order_by(ContentRevision.revision.desc())).all()
