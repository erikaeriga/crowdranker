# coding: utf8

import util

@auth.requires_login()
def subopen_index():
    props = db(db.user_properties.email == auth.user.email).select(db.user_properties.contests_can_submit).first()
    if props == None: 
        l = []
    else:
        l = util.get_list(props.contests_can_submit)
    q_all = ((db.contest.open_date < datetime.utcnow())
             & (db.contest.close_date > datetime.utcnow()) 
             & (db.contest.is_active == True) 
             & (db.contest.submit_constraint == None)
             )
    c_all = db(q_all).select(db.contest.id).as_list()
    if len(l) > 0:
        q_user = ((db.contest.open_date < datetime.utcnow())
                  & (db.contest.close_date > datetime.utcnow())
                  & (db.contest.is_active == True)
                  & (db.contest.id.belongs(l))
                  )
        c_user = db(q_user).select(db.contest.id).as_list()
        c = util.union_id_list(c_all, c_user)
    else:
        c = util.id_list(c_all)
    q = (db.contest.id.belongs(c))
    grid = SQLFORM.grid(q,
        field_id=db.contest.id,
        fields=[db.contest.name, db.contest.close_date],
        csv=False,
        details=True,
        create=False,
        editable=False,
        deletable=False,
        links=[dict(header='Submit', 
            body = lambda r: A(T('submit'), _href=URL('submission', 'submit', args=[r.id])))],
        )
    return dict(grid=grid)


@auth.requires_login()
def rateopen_index():
    props = db(db.user_properties.email == auth.user.email).select(db.user_properties.contests_can_rate).first()
    if props == None:
        l = []
    else:
        l = util.get_list(props.contests_can_rate)
    q_all = ((db.contest.rate_open_date < datetime.utcnow())
             & (db.contest.rate_close_date > datetime.utcnow()) 
             & (db.contest.is_active == True) 
             & (db.contest.rate_constraint == None)
             )
    c_all = db(q_all).select(db.contest.id).as_list()
    if len(l) > 0:
        q_user = ((db.contest.rate_open_date < datetime.utcnow())
                  & (db.contest.rate_close_date > datetime.utcnow())
                  & (db.contest.is_active == True)
                  & (db.contest.id.belongs(l))
                  )
        c_user = db(q_user).select(db.contest.id).as_list()
        c = util.union_id_list(c_all, c_user)
    else:
        c = util.id_list(c_all)
    q = (db.contest.id.belongs(c))
    grid = SQLFORM.grid(q,
        field_id=db.contest.id,
        fields=[db.contest.name, db.contest.close_date],
        csv=False,
        details=True,
        create=False,
        editable=False,
        deletable=False,
        links=[dict(header='Rate', 
            body = lambda r: A(T('rate'), _href=URL('rating', 'rate', args=[r.id])))],
        )
    return dict(grid=grid)

                
@auth.requires_login()
def submitted_index():
    props = db(db.user_properties.email == auth.user.email).select(db.user_properties.contests_has_submitted).first()
    if props == None: 
        l = []
    else:
        l = util.id_list(util.get_list(props.contests_has_submitted))
    q = (db.contest.id.belongs(l))
    grid = SQLFORM.grid(q,
        field_id=db.contest.id,
        fields=[db.contest.name],
        csv=False,
        details=True,
        create=False,
        editable=False,
        deletable=False,
        links=[dict(header='Feedback', 
            body = lambda r: A(T('view ratings and feedback'), _href=URL('feedback', 'view', args=[r.id])))],
        )
    return dict(grid=grid)

        
@auth.requires_login()
def managed_index():
    props = db(db.user_properties.email == auth.user.email).select(db.user_properties.contests_can_manage).first()
    if props == None:
        managed_contest_list = []
        managed_user_lists = None
    else:
        managed_contest_list = util.get_list(props.contests_can_manage)
        managed_user_lists = util.get_list(props.managed_user_lists)
    q = (db.contest.id.belongs(managed_contest_list))    
    # Constrains the user lists to those managed by the user.
    list_q = (db.user_list.id.belongs(managed_user_lists))
    db.contest.submit_constraint.requires = IS_IN_DB(
        db(list_q), 'user_list.id', '%(name)s', zero=T('-- Everybody --'), required=False)
    db.contest.rate_constraint.requires = IS_IN_DB(
        db(list_q), 'user_list.id', '%(name)s', zero=T('-- Everybody --'), required=False)
    # Keeps track of old managers, if this is an update.
    if len(request.args) > 2 and request.args[-3] == 'edit':
        c = db.contest[request.args[-1]]
        old_managers = c.managers
        old_submit_constraint = c.submit_constraint
        old_rate_constraint = c.rate_constraint

    else:
        old_managers = []
        old_submit_constraint = None
        old_rate_constraint = None
    if len(request.args) > 0 and (request.args[0] == 'edit' or request.args[0] == 'new'):
        # Let's add a bit of help for editing
        db.contest.is_active.comment = 'Uncheck to prevent all access to this contest.'
        db.contest.managers.comment = 'Email addresses of contest managers.'
        db.contest.name.comment = 'Name of the contest'
        db.contest.featured_submissions.comment = (
            'Enable raters to flag submissions as featured. '
            'Submitters can request to see featured submissions.')
    grid = SQLFORM.grid(q,
        field_id=db.contest.id,
        fields=[db.contest.name, db.contest.managers, db.contest.is_active],
        csv=False,
        details=True,
        create=True,
        deletable=False, # Disabled; cannot delete contests with submissions.
        onvalidation=validate_contest,
        oncreate=create_contest,
        onupdate=update_contest(old_managers, old_submit_constraint, old_rate_constraint),
        )
    return dict(grid=grid)
    
def validate_contest(form):
    """Validates the form contest, splitting managers listed on the same line."""
    form.vars.managers = util.normalize_email_list(form.vars.managers)
    if auth.user.email not in form.vars.managers:
        form.vars.managers = [auth.user.email] + form.vars.managers
    

def add_contest_to_user_managers(id, user_list):
    for m in user_list:
        u = db(db.user_properties.email == m).select(db.user_properties.contests_can_manage).first()
        if u == None:
            # We never heard of this user, but we still create the permission.
            logger.debug("Creating user properties for email:" + str(m) + "<")
            db.user_properties.insert(email=m)
            db.commit()
            l = []
        else:
            l = u.contests_can_manage
        l = util.list_append_unique(l, id)
        db(db.user_properties.email == m).update(contests_can_manage = l)
    db.commit()
        
def add_contest_to_user_submit(id, user_list):
    for m in user_list:
        u = db(db.user_properties.email == m).select(db.user_properties.contests_can_submit).first()
        if u == None:
            # We never heard of this user, but we still create the permission.
            logger.debug("Creating user properties for email:" + str(m) + "<")
            db.user_properties.insert(email=m)
            db.commit()
            l = []
        else:
            l = u.contests_can_submit
        l = util.list_append_unique(l, id)
        db(db.user_properties.email == m).update(contests_can_submit = l)
    db.commit()
        
def add_contest_to_user_rate(id, user_list):
    for m in user_list:
        u = db(db.user_properties.email == m).select(db.user_properties.contests_can_rate).first()
        if u == None:
            # We never heard of this user, but we still create the permission.
            logger.debug("Creating user properties for email:" + str(m) + "<")
            db.user_properties.insert(email=m)
            db.commit()
            l = []
        else:
            l = u.contests_can_rate
        l = util.list_append_unique(l, id)
        db(db.user_properties.email == m).update(contests_can_rate = l)
    db.commit()

def delete_contest_from_managers(id, managers):
    for m in managers:
        u = db(db.user_properties.email == m).select(db.user_properties.contests_can_manage).first()
        if u != None:
            l = util.list_remove(u.contests_can_manage, id)
            db(db.user_properties.email == m).update(contests_can_manage = l)
    db.commit()
       
def delete_contest_from_submitters(id, users):
    for m in users:
        u = db(db.user_properties.email == m).select(db.user_properties.contests_can_submit).first()
        if u != None:
            l = util.list_remove(u.contests_can_submit, id)
            db(db.user_properties.email == m).update(contests_can_submit = l)
    db.commit()
       
def delete_contest_from_raters(id, users):
    for m in users:
        u = db(db.user_properties.email == m).select(db.user_properties.contests_can_rate).first()
        if u != None:
            l = util.list_remove(u.contests_can_rate, id)
            db(db.user_properties.email == m).update(contests_can_rate = l)
    db.commit()
                        
def create_contest(form):
    """Processes the creation of a context, propagating the effects."""
    # First, we need to add the context for the new managers.
    add_contest_to_user_managers(form.vars.id, form.vars.managers)
    # If there is a submit constraint, we need to allow all the users
    # in the list to submit.
    if not util.is_none(form.vars.submit_constraint):
        logger.debug("form.vars.submit_contraints is:" + str(form.vars.submit_constraint) + "<")
        user_list = db.user_list[form.vars.submit_constraint].email_list
        # We need to add everybody in that list to submit.
        add_contest_to_user_submit(form.vars.id, user_list)
    # If there is a rating constraint, we need to allow all the users
    # in the list to rate.
    if not util.is_none(form.vars.rate_constraint):
        user_list = db.user_list[form.vars.rate_constraint].email_list
        add_contest_to_user_rate(form.vars.id, user_list)
                
def update_contest(old_managers, old_submit_constraint, old_rate_constraint):
    """A contest is being updated.  We need to return a callback for the form,
    that will produce the proper update, taking into account the change in permissions."""
    def f(form):
        # Managers.
        add_contest_to_user_managers(form.vars.id, util.list_diff(form.vars.managers, old_managers))
        delete_contest_from_managers(form.vars.id, util.list_diff(old_managers, form.vars.managers))
        # Submitters.
        if old_submit_constraint != form.vars.submit_constraint:
            # We need to update.
            if not util.is_none(old_submit_constraint):
                user_list = db.user_list[old_submit_constraint]
                delete_contest_from_submitters(form.vars.id, user_list)
            if not util.is_none(form.vars.submit_constraint):
                user_list = db.user_list[form.vars.submit_constraint]
                add_contest_to_user_submit(form.vars.id, user_list)
        # Raters.
        if old_rate_constraint != form.vars.rate_constraint:
            # We need to update.
            if not util.is_none(old_rate_constraint):
                user_list = db.user_list[old_rate_constraint]
                delete_contest_from_raters(form.vars.id, user_list)
            if not util.is_none(form.vars.rate_constraint):
                user_list = db.user_list[form.vars.rate_constraint]
                add_contest_to_user_rate(form.vars.id, user_list)
    return f
                
def delete_contest(table, id):
    c = db.contest[id]
    delete_contest_from_managers(id, c.managers)
    if not util.is_none(c.submit_constraint):
        user_list = db.user_list[c.submit_constraint]
        delete_contest_from_submitters(id, user_list)
    if not util.is_none(c.rate_constraint):
        user_list = db.user_list[c.rate_constraint]
        delete_contest_from_raters(id, user_list)
