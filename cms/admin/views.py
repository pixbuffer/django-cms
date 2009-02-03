from django.shortcuts import get_object_or_404, render_to_response
from django.http import HttpResponse, Http404
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.translation import ugettext_lazy as _
from django.template.context import RequestContext

from cms import settings
from cms.models import Page, Title, CMSPlugin
from cms.plugin_pool import plugin_pool
from cms.utils import auto_render


def change_status(request, page_id):
    """
    Switch the status of a page
    """
    if request.method == 'POST':
        page = Page.objects.get(pk=page_id)
        if page.has_publish_permission(request):
            if page.status == Page.DRAFT:
                page.status = Page.PUBLISHED
            elif page.status == Page.PUBLISHED:
                page.status = Page.DRAFT
            page.save()    
            return HttpResponse(unicode(page.status))
    raise Http404
change_status = staff_member_required(change_status)

def change_innavigation(request, page_id):
    """
    Switch the in_navigation of a page
    """
    if request.method == 'POST':
        page = Page.objects.get(pk=page_id)
        if page.has_page_permission(request):
            if page.in_navigation:
                page.in_navigation = False
                val = 0
            else:
                page.in_navigation = True
                val = 1
            page.save()
            return HttpResponse(unicode(val))
    raise Http404
change_status = staff_member_required(change_status)

#def modify_content(request, page_id, content_id, language_id):
#    if request.method == 'POST':
#        content = request.POST.get('content', False)
#        if not content:
#            raise Http404
#        page = Page.objects.get(pk=page_id)
#        if not page.has_page_permission(request):
#            raise Http404
#        #if settings.CMS_CONTENT_REVISION: #TODO: implement with revisions
#        #    Content.objects.create_content_if_changed(page, language_id,
#        #                                              content_id, content)
#        #else:
#        if content_id.lower() not in ['title', 'slug']:
#            Content.objects.set_or_create_content(page, language_id,
#                                                  content_id, content)
#        else:
#            if content_id.lower() == "title":
#                Title.objects.set_or_create(page, language_id, slug=None, title=content)
#            elif content_id.lower() == "slug":
#                Title.objects.set_or_create(page, language_id, slug=content, title=None)
#        return HttpResponse('ok')
#    raise Http404
#modify_content = staff_member_required(modify_content)

#def get_content(request, page_id, content_id):
#    content_instance = get_object_or_404(Content, pk=content_id)
#    return HttpResponse(content_instance.body)
#get_content = staff_member_required(get_content)
#get_content = auto_render(get_content)

if 'reversion' in settings.INSTALLED_APPS:
    from reversion import revision


    # Make changes to your models here.
    

def add_plugin(request):
    if request.method == "POST":
        
        print "add plugin"
        page_id = request.POST['page_id']
        page = get_object_or_404(Page, pk=page_id)
        placeholder = request.POST['placeholder']
        plugin_type = request.POST['plugin_type']
        language = request.POST['language']
        
        position = CMSPlugin.objects.filter(page=page, language=language, placeholder=placeholder).count()
        plugin = CMSPlugin(page=page, language=language, plugin_type=plugin_type, position=position, placeholder=placeholder) 
        plugin.save()
        request.method = "GET"
        if 'reversion' in settings.INSTALLED_APPS:
            page.save()
            save_all_plugins(page)
            revision.user = request.user
            plugin_name = unicode(plugin_pool.get_plugin(plugin_type).name)
            revision.comment = _(u"%(plugin_name)s plugin added to %(placeholder)s") % {'plugin_name':plugin_name, 'placeholder':placeholder}       
        return HttpResponse(str(plugin.pk))
    raise Http404

if 'reversion' in settings.INSTALLED_APPS:
    add_plugin = revision.create_on_success(add_plugin)

def edit_plugin(request, plugin_id):
    if not 'history' in request.path:
        cms_plugin = get_object_or_404(CMSPlugin, pk=plugin_id)
        instance, plugin_class = cms_plugin.get_plugin_instance()
    else:
        plugin_id = int(plugin_id)
        from reversion.models import Version
        version_id = request.path.split("/edit-plugin/")[0].split("/")[-1]
        version = get_object_or_404(Version, pk=version_id)
        revs = [related_version.object_version for related_version in version.revision.version_set.all()]
        #print revs
        for rev in revs:
            obj = rev.object
            if obj.__class__ == CMSPlugin and obj.pk == plugin_id:
                cms_plugin = obj
                break
        inst, plugin_class = cms_plugin.get_plugin_instance()
        instance = None
        for rev in revs:
            obj = rev.object
            if obj.__class__ == inst.__class__ and int(obj.pk) == plugin_id:
                instance = obj
                break
    if request.method == "POST":
        if instance:
            form = plugin_class.form(request.POST, request.FILES, instance=instance)
        else:
            form = plugin_class.form(request.POST, request.FILES)
        if form.is_valid():
            if 'history' in request.path:
                return render_to_response('admin/cms/page/plugin_forms_history.html', {'CMS_MEDIA_URL':settings.CMS_MEDIA_URL, 'is_popup':True},RequestContext(request))
            inst = form.save(commit=False)
            inst.pk = cms_plugin.pk
            inst.page = cms_plugin.page
            inst.position = cms_plugin.position
            inst.placeholder = cms_plugin.placeholder
            inst.language = cms_plugin.language
            inst.plugin_type = cms_plugin.plugin_type
            inst.save()
            inst.page.save()
            if 'reversion' in settings.INSTALLED_APPS:
                save_all_plugins(inst.page, [inst.pk])
                revision.user = request.user
                plugin_name = unicode(plugin_pool.get_plugin(inst.plugin_type).name)
                revision.comment = _(u"%(plugin_name)s plugin edited at position %(position)s in %(placeholder)s") % {'plugin_name':plugin_name, 'position':inst.position, 'placeholder':inst.placeholder}
            return render_to_response('admin/cms/page/plugin_forms_ok.html',{'CMS_MEDIA_URL':settings.CMS_MEDIA_URL, 'plugin':cms_plugin, 'is_popup':True},RequestContext(request))
        else:
            pass
            #print request.POST
    else:
        if instance:
            form = plugin_class.form(instance=instance)
        else:
            form = plugin_class.form() 
    if plugin_class.form_template:
        template = plugin_class.form_template
    else:
        template = 'admin/cms/page/plugin_forms.html'
    return render_to_response(template, {'form':form, 'plugin':cms_plugin, 'instance':instance, 'is_popup':True, 'CMS_MEDIA_URL':settings.CMS_MEDIA_URL}, RequestContext(request))

if 'reversion' in settings.INSTALLED_APPS:
    edit_plugin = revision.create_on_success(edit_plugin)

def move_plugin(request):
    if request.method == "POST" and not 'history' in request.path:
        pos = 0
        page = None
        for id in request.POST['ids'].split("_"):
            plugin = CMSPlugin.objects.get(pk=id)
            if not page:
                page = plugin.page
            if plugin.position != pos:
                plugin.position = pos
                plugin.save()
            pos += 1
        if page and 'reversion' in settings.INSTALLED_APPS:
            page.save()
            save_all_plugins(page)
            revision.user = request.user
            revision.comment = unicode(_(u"Plugins where moved")) 
        return HttpResponse(str("ok"))
    else:
        raise Http404
    
if 'reversion' in settings.INSTALLED_APPS:
    move_plugin = revision.create_on_success(move_plugin)
  
def remove_plugin(request):
    if request.method == "POST" and not 'history' in request.path:
        plugin_id = request.POST['plugin_id']
        plugin = get_object_or_404(CMSPlugin, pk=plugin_id)
        page = plugin.page
        plugin.delete()
        if 'reversion' in settings.INSTALLED_APPS:
            save_all_plugins(page)
            page.save()
            revision.user = request.user
            plugin_name = unicode(plugin_pool.get_plugin(plugin.plugin_type).name)
            revision.comment = _(u"%(plugin_name)s plugin at position %(position)s in %(placeholder)s was deleted.") % {'plugin_name':plugin_name, 'position':plugin.position, 'placeholder':plugin.placeholder}
        return HttpResponse(str(plugin_id))
    raise Http404

if 'reversion' in settings.INSTALLED_APPS:
    remove_plugin = revision.create_on_success(remove_plugin)
    
def save_all_plugins(page, excludes=None):
    for plugin in CMSPlugin.objects.filter(page=page):
        if excludes:
            if plugin.pk in excludes:
                continue
        plugin.save()
        
def revert_plugins(request, version_id):
    from reversion.models import Version
    
    version = get_object_or_404(Version, pk=version_id)
    revs = [related_version.object_version for related_version in version.revision.version_set.all()]
    plugin_list = []
    page = None
    for rev in revs:
        obj = rev.object
        print obj.__class__
        if obj.__class__ == CMSPlugin:
            if obj.language == language and obj.placeholder == placeholder.name:
                plugin_list.append(rev.object)
        if obj.__class__ == Page:
            page = obj
    current_plugins = CMSPlugin.objects.filter(page=page)