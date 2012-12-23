# coding: utf8

import util
import ranker

@auth.requires_login()
def my_submissions_index():
    """Index of submissions to a context."""
    # Gets information on this specific contest.
    c = db.contest(request.args(0)) or redirect(URL('default', 'index'))
    # Gets the list of all submissions to the given contest.
    q = ((db.submission.author == auth.user_id) 
            & (db.submission.contest_id == c.id))
    db.submission.contest_id.readable = False
    db.submission.title.readable = False
    grid = SQLFORM.grid(q,
        args=request.args[1:],
        field_id = db.submission.id,
        fields = [db.submission.id, db.submission.title, db.submission.contest_id],
        create = False,
        user_signature = False,
        details = False,
        csv = False,
        editable = False,
        deletable = False,
        links = [
            dict(header = T('Contest'), body = lambda r:
                A(T('contest'), _href=URL('contests', 'view_contest', args=[r.contest_id]))),
            dict(header = T('Submission'), body = lambda r:
                A(T(r.title), _href=URL('view_own_submission', args=[r.id]))),
            dict(header = T('Feedback'), body = lambda r:
                A(T('feedback'), _href=URL('feedback', 'submission', args=[r.id]))),
            ]
        )
    # TODO(luca): check can_add to see if we can include a link to submit, below.
    return dict(grid=grid, contest=c)
        

@auth.requires_login()
def submit():
    # Gets the information on the contest.
    c = db.contest(request.args[0]) or redirect(URL('default', 'index'))
    # Gets information on the user.
    props = db(db.user_properties.email == auth.user.email).select().first()
    if props == None: 
        contest_ids = []
    else:
        contest_ids = util.get_list(props.contests_can_submit)
    # Is the contest open for submission?
    if not (c.submit_constraint == None or c.id in contest_ids):
        redirect('closed', args=['permission'])
    t = datetime.utcnow()
    if not (c.is_active and c.open_date <= t and c.close_date >= t):
        redirect('closed', args=['deadline'])
    # Ok, the user can submit.  Looks for previous submissions.
    sub = db((db.submission.author == auth.user_id) & (db.submission.contest_id == c.id)).select().first()
    if sub != None and not c.allow_multiple_submissions:
        session.flash = T('You have already submitted to this contest.')
        redirect(URL('my_submissions_index', args=[c.id]))
    # The author can access the title.
    db.submission.title.readable = db.submission.title.writable = True
    # Produces an identifier for the submission.
    db.submission.identifier.default = util.get_random_id()
    # TODO(luca): check that it is fine to do the download link without parameters.
    form = SQLFORM(db.submission,upload=URL('download_auhor', args=[None]))
    form.vars.contest_id = c.id
    if request.vars.content != None and request.vars.content != '':
        form.vars.original_filename = request.vars.content.filename
    if form.process().accepted:
        # Adds the contest to the list of contests where the user submitted.
        # TODO(luca): Enable users to delete submissions.  But this is complicated; we need to 
        # delete also their quality information etc.  For the moment, no deletion.
        submitted_ids = util.id_list(util.get_list(props.contests_has_submitted))
        submitted_ids = util.list_append_unique(submitted_ids, c.id)
        props.update_record(contests_has_submitted = submitted_ids)
        # Assigns the initial distribution to the submission.
        avg, stdev = ranker.get_init_average_stdev()
        db.quality.insert(contest_id=c.id, submission_id=form.vars.id, user_id=auth.user_id, average=avg, stdev=stdev)
        db.commit()
        session.flash = T('Your submission has been accepted.')
        redirect(URL('feedback', 'index', args=['all']))
    return dict(form=form)
         

@auth.requires_login()
def view_submission():
    """Allows viewing a submission by someone who has the task to review it.
    This function is accessed by task id, not submission id, to check access
    and anonymize the submission."""
    # TODO(mbrich): here we need to be able to download the submission, and:
    # * For the author, download it under the original name.
    # * For a user, download it as t.submission_name + the original extension of the file.
    v = validate_task(request.args(0), auth.user_id)
    if v == None:
        session.flash(T('Not authorized.'))
        redirect(URL('default', 'index'))
    (t, subm, cont) = v
    # Shows the submission, except for the title (unless we are showing it to the author).
    if subm.author != auth.user_id:
        db.submission.title.readable = False
    # We want to rename the submission content, so let us not display it as part of the form.
    db.submission.content.readable = False
    form = SQLFORM(db.submission, record = subm, readonly=True)
    download_link = None
    if subm.content != None and len(subm.content) > 0:
        download_link = URL('download_reviewer', args=[t.id, subm.content])    
    return dict(form=form, download_link=download_link)

   
@auth.requires_login()
def view_own_submission():
    """Allows viewing a submission by the submission owner.
    The argument is the submission id."""
    subm = db.submission(request.args(0)) or redirect(URL('default', 'index'))
    if subm.author != auth.user_id:
        session.flash = T('You cannot view this submission.')
        redirect(URL('default', 'index'))
    # If the contest is still open for submissions, then we allow editing of the submission.
    c = db.contest(subm.contest_id) or redirect(URL('default', 'index'))
    t = datetime.utcnow()
    download_link = None
    if (c.is_active and c.open_date <= t and c.close_date >= t):
        form = SQLFORM(db.submission, subm, upload=URL('download_author', args=[subm.id]))
        if request.vars.content != None and request.vars.content != '':
            form.vars.original_filename = request.vars.content.filename
        if form.process().accepted:
            session.flash = T('Your submission has been updated.')
            redirect(URL('feedback', 'index', args=['all']))
    else:
        db.submission.content.readable = False
        form = SQLFORM(db.submission, subm, readonly=True, upload=URL('download_author', args=[subm.id]), buttons=[])
        if subm.content != None and len(subm.content) > 0:
            download_link = URL('download', args=[subm.content], vars=dict(s=subm.id))
    return dict(form=form, subm=subm, download_link=download_link)


def validate_task(t_id, user_id):
    """Validates that user_id can do the reviewing task t."""
    t = db.task(request.args(0))
    if t == None:
        return None
    if t.user_id != user_id:
        return None
    subm = db.submission(t.submission_id)
    if subm == None:
        return None
    c = db.contest(subm.contest_id)
    if c == None:
        return None
    t = datetime.utcnow()
    if c.rate_open_date > t or c.rate_close_date < t:
        return None
    return (t, s, c)



def download_submission( src_filename, dst_filename = None, is_attachment = False ):
    # src_filename - the requested filename
    # dst_filename - filename the user sees. Blank if not given.
    # is_attachment is whether to force a download instead of stream.

    import gluon.fileutils
    import mimetypes

    # Builds the relative path string from our current dir, to the uploads
    # dir including the src_filename.  This will be used to open the file.
    src_path = os.path.join( request.folder,'uploads/', src_filename )

    # (Mike) TODO: Make sure this module works as expected on GAE.
    # (Mike) Future TODO: This function only checks filename. Need a function
    # that works on GAE AND also checks file contents to determine mime.
    response.headers['ContentType'] = mimetypes.guess_type( src_filename )

    if ( is_attachment == True ):
        if ( dst_filename != None ):
             # Filter out anything that shouldn't be in a filename, replace spaces with 
            # underscores, and convert to lowercase.
            dst_filename = gluon.fileutils.cleanpath( dst_filename.replace( ' ', '_' ).lower() )
            response.headers['Content-Disposition'] = "attachment; Filename=" + dst_filename

        else:
            response.headers['Content-Disposition'] = "attachment"


    return response.stream( open( src_path, "rb" ), chunk_size = 4096 )

	
@auth.requires_login()
def download_author():

    # The user must be the owner of the submission.
    subm = db.submission(request.args(0))
	
	# Internal error if we dont deal with subm being empty
    if (subm  == None):
        redirect(URL('default', 'index' ) )
	
    if subm.author != auth.user_id:
        session.flash = T('Not authorized.')
        redirect(URL('default', 'index'))
    request.args = request.args[1:]

    return response.download(request, db)
	

@auth.requires_login()
def download_reviewer():
    # Checks that the reviewer has access.
    v = validate_task(request.args(0), auth.user_id)
    if v == None:
        session.flash = T('Not authorized.')
        redirect(URL('default', 'index'))
    (t, s, c) = v

    import os

    # Get the ext of the original file
    original_ext = os.path.splitext( s.original_filename )[1]


    # file_alias is the filename that will be displayed to the user.
    # The way we build the alias depends on the contest settings,
    # starting with anonymized submissions.
    # NOTE: Not sure whether task names are working. Needs testing.
    if ( c.submissions_are_anonymized == True ):
        file_alias = c.name + '_' + ( t.submission_name if t != None else '' )  + original_ext

    else:
        # If title_is_file_name is set, then we use that as the alias,
        # otherwise we use the original filename.
        if ( c.submission_title_is_file_name == True ):
            file_alias = s.title + original_ext
    
        else:
            file_alias = s.original_filename


    #return response.download(request, db, attachment=False)
    return download_submission( s, file_alias )
	