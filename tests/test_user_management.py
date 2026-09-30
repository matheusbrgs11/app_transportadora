def test_admin_manages_staff_access_and_sessions(context):
    client,company,other,login,_,_=context
    admin=login()
    foreign=login(other)
    created=client.post('/usuarios',headers=admin,json={
        'nome':'Agenda','login':'agenda','perfil':'agendamento','senha':'senha-segura-teste'})
    assert created.status_code==201,created.text
    user_id=created.json()['id']
    session=login(usuario='agenda')
    listing=client.get('/usuarios',headers=admin)
    assert listing.status_code==200
    assert any(u['id']==user_id for u in listing.json()['items'])
    assert client.get('/usuarios',headers=session).status_code==403
    assert client.put(f'/usuarios/{user_id}/acesso',headers=foreign,json={'ativo':False}).status_code==404
    assert client.post(f'/usuarios/{user_id}/senha',headers=foreign,json={'nova_senha':'nova-senha-segura'}).status_code==404
    blocked=client.put(f'/usuarios/{user_id}/acesso',headers=admin,json={'ativo':False})
    assert blocked.status_code==200 and blocked.json()['ativo'] is False
    assert client.get('/auth/me',headers=session).status_code==401
    assert client.post('/auth/login',json={'empresa_id':str(company),'usuario_login':'agenda','senha':'senha-segura-teste'}).status_code==401
    assert client.put(f'/usuarios/{user_id}/acesso',headers=admin,json={'ativo':True}).status_code==200
    session=login(usuario='agenda')
    reset=client.post(f'/usuarios/{user_id}/senha',headers=admin,json={'nova_senha':'nova-senha-segura'})
    assert reset.status_code==204,reset.text
    assert client.get('/auth/me',headers=session).status_code==401
    login(usuario='agenda',senha='nova-senha-segura')


def test_change_own_password_requires_old_password_and_revokes_sessions(context):
    client,_,_,login,_,_=context
    first=login()
    second=login()
    user_id=client.get('/auth/me',headers=first).json()['id']
    assert client.put(f'/usuarios/{user_id}/acesso',headers=first,json={'ativo':False}).status_code==409
    assert client.post(f'/usuarios/{user_id}/senha',headers=first,json={'nova_senha':'nova-senha-segura'}).status_code==409
    wrong=client.post('/auth/senha',headers=first,json={'senha_atual':'incorreta','nova_senha':'nova-senha-segura'})
    assert wrong.status_code==400
    assert client.get('/auth/me',headers=first).status_code==200
    changed=client.post('/auth/senha',headers=first,json={'senha_atual':'senha-segura-teste','nova_senha':'nova-senha-segura'})
    assert changed.status_code==204,changed.text
    assert client.get('/auth/me',headers=first).status_code==401
    assert client.get('/auth/me',headers=second).status_code==401
    login(senha='nova-senha-segura')
