import rdflib
from rdflib import *
from rdflib.namespace import NamespaceManager
from rdflib.extras.infixowl import *

import json
import sys

def get_prefix(ns, graph):
    (base, _, fragment) = str(ns)[:-1:].rpartition('/')

    domain = ns.partition('http://')[2].partition('/')[0]
    vendor = domain.rpartition('.')[0].partition('-')[0]

    prefix = vendor + '_' + fragment

    for p, n in NamespaceManager(graph).namespaces():
        if prefix == p and str(ns) != str(n):
            prefix = vendor + '_' + base.rpartition('/')[2] + '_' + fragment

    return prefix

def get_class(aps_type_id, graph, exists=None):
    (class_id, _, version) = aps_type_id.rpartition('/')
    if version and '.' not in version:
        class_id = aps_type_id

    ns = Namespace(class_id.rpartition('/')[0] + '/')
    prefix = get_prefix(ns, graph)
    NamespaceManager(graph).bind(prefix, ns, override=False)

    cls = rdflib.URIRef(class_id)
    if exists or exists is None:
        cls = CastClass(cls, graph) or cls
    else:
        cls = Class(cls, graph=graph)

    return cls

def import_class(aps_schema, graph, validate_types=False):
    cls = get_class(aps_schema['id'], graph, False)

    ns = Namespace(cls.identifier + '/')
    prefix = get_prefix(ns, graph)
    NamespaceManager(graph).bind(prefix, ns, override=False)

    for impl in aps_schema.get('implements', []):
        impl_cls = get_class(impl, graph, exists=validate_types or None)
        if validate_types and not impl_cls:        
            raise Exception("type %s not imported" % impl)

        cls.subClassOf = [impl_cls]

    if aps_schema.has_key('properties'):
        for prop_key, prop in aps_schema['properties'].items():
            Property(ns[prop_key],
                baseType=OWL_NS.DatatypeProperty,
                graph=graph)

    if aps_schema.has_key('relations'):
        for rel_key, rel in aps_schema['relations'].items():
            type = rel['type']
            rel_cls_list = []
            inverse_of = None

            for type in isinstance(type, list) and type or [type]:
                rel_cls = get_class(type, graph, exists=validate_types or None)
                if validate_types and not isinstance(rel_cls, Class):
                    raise Exception("type %s not imported" % type)
                rel_cls_list.append(rel_cls)

                if isinstance(rel_cls, Class):
                    parents = [cls.identifier]
                    parents += [p.identifier for p in cls.parents]

                    for prop, _, _ in graph.triples_choices(
                        (None, RDFS.range, parents)):
                        if prop == ns[rel_key]:
                            continue

                        rev_cls = next(graph.objects(prop, RDFS.domain), None)
                        if rev_cls is None:
                            continue

                        rev_cls = get_class(rev_cls, graph)

                        if rev_cls and isinstance(rev_cls, Class):
                            parents = [rev_cls.identifier]
                            parents += [p.identifier for p in rev_cls.parents]

                            if rel_cls.identifier in parents:
                                inverse_of = prop

            prop = Property(ns[rel_key],
                domain=cls,
                range=rel_cls_list,
                inverseOf=inverse_of,
                graph=graph)

            if not validate_types:
                if rel.get('required', False):
                    cls.subClassOf = [Restriction(prop,
                        cardinality=Literal(1),
                        graph=graph)]

    return cls

graph = Graph()
CommonNSBindings(graph)

for arg in sys.argv[1:]:
    import_class(json.loads(open(arg).read()), graph)

for arg in sys.argv[1:]:
    import_class(json.loads(open(arg).read()), graph, validate_types=True)

print(graph.serialize(format='turtle'))
