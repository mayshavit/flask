# -*- coding: utf-8 -*-
"""
    flask.templating
    ~~~~~~~~~~~~~~~~

    Implements the bridge to Jinja2.

    :copyright: (c) 2011 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
import posixpath
from jinja2 import BaseLoader, Environment as BaseEnvironment, \
     TemplateNotFound

from .globals import _request_ctx_stack
from .signals import template_rendered
from .module import blueprint_is_module


def _default_template_ctx_processor():
    """Default template context processor.  Injects `request`,
    `session` and `g`.
    """
    reqctx = _request_ctx_stack.top
    return dict(
        config=reqctx.app.config,
        request=reqctx.request,
        session=reqctx.session,
        g=reqctx.g
    )


class Environment(BaseEnvironment):
    """Works like a regular Jinja2 environment but has some additional
    knowledge of how Flask's blueprint works so that it can prepend the
    name of the blueprint to referenced templates if necessary.
    """

    def __init__(self, app, **options):
        if 'loader' not in options:
            options['loader'] = app.create_global_jinja_loader()
        BaseEnvironment.__init__(self, **options)
        self.app = app
        
    def _load_template(self, name, globals):
        loader = None
        reqctx = _request_ctx_stack.top
        if reqctx.request.blueprint == None:
            cache_name = 'app::' + name
            loader = reqctx.app.jinja_loader
        else:
            cache_name = reqctx.request.blueprint + '::' + name
            loader = reqctx.app.blueprints[reqctx.request.blueprint].jinja_loader
            
        if self.loader is None and self.loader is None:
            raise TypeError('no loader for this environment specified')
        if self.cache is not None:
            template = self.cache.get(cache_name)
            if template is not None and (not self.auto_reload or \
                                         template.is_up_to_date):
                return template
            
        template = None
        if loader is not None:
            try:
                template = loader.load(self, name, globals)
            except TemplateNotFound:
                pass
                
        if template is None:
            template = self.loader.load(self, name, globals)
        
        if self.cache is not None:
            self.cache[cache_name] = template
            
        return template


class DispatchingJinjaLoader(BaseLoader):
    """A loader that looks for templates in the application and all
    the blueprint folders.
    """

    def __init__(self, app):
        self.app = app

    def get_source(self, environment, template):
        for loader, local_name in self._iter_loaders(template):
            try:
                return loader.get_source(environment, local_name)
            except TemplateNotFound:
                pass

        raise TemplateNotFound(template)

    def _iter_loaders(self, template):
        loader = self.app.jinja_loader
        if loader is not None:
            yield loader, template

        # old style module based loaders in case we are dealing with a
        # blueprint that is an old style module
        try:
            module, local_name = posixpath.normpath(template).split('/', 1)
            blueprint = self.app.blueprints[module]
            if blueprint_is_module(blueprint):
                loader = blueprint.jinja_loader
                if loader is not None:
                    yield loader, local_name
        except (ValueError, KeyError):
            pass

        for blueprint in self.app.blueprints.itervalues():
            if blueprint_is_module(blueprint):
                continue
            loader = blueprint.jinja_loader
            if loader is not None:
                yield loader, template

    def list_templates(self):
        result = set()
        loader = self.app.jinja_loader
        if loader is not None:
            result.update(loader.list_templates())

        for name, blueprint in self.app.blueprints.iteritems():
            loader = blueprint.jinja_loader
            if loader is not None:
                for template in loader.list_templates():
                    prefix = ''
                    if blueprint_is_module(blueprint):
                        prefix = name + '/'
                    result.add(prefix + template)

        return list(result)


def _render(template, context, app):
    """Renders the template and fires the signal"""
    rv = template.render(context)
    template_rendered.send(app, template=template, context=context)
    return rv


def render_template(template_name_or_list, **context):
    """Renders a template from the template folder with the given
    context.

    :param template_name_or_list: the name of the template to be
                                  rendered, or an iterable with template names
                                  the first one existing will be rendered
    :param context: the variables that should be available in the
                    context of the template.
    """
    ctx = _request_ctx_stack.top
    ctx.app.update_template_context(context)
    return _render(ctx.app.jinja_env.get_or_select_template(template_name_or_list),
                   context, ctx.app)


def render_template_string(source, **context):
    """Renders a template from the given template source string
    with the given context.

    :param template_name: the sourcecode of the template to be
                          rendered
    :param context: the variables that should be available in the
                    context of the template.
    """
    ctx = _request_ctx_stack.top
    ctx.app.update_template_context(context)
    return _render(ctx.app.jinja_env.from_string(source),
                   context, ctx.app)
