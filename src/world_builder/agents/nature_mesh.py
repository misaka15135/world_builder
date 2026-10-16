"""046 source triangle meshes, yaw transforms and deterministic GLB encoding."""
import json
import math
import struct


def transform(point,pose):
    x,y,z=point;c,s=math.cos(math.radians(pose["yaw"])),math.sin(math.radians(pose["yaw"]))
    return [pose["x"]+c*(x-pose["ox"])-s*(y-pose["oy"]),
            pose["y"]+s*(x-pose["ox"])+c*(y-pose["oy"]),z+pose["dz"]]


def mesh(name,group,material,vertices,triangles,normals=None,solid=True,component=None):
    if normals is None:
        # Flat triangles for architectural/rock faces.
        out=[];ns=[];indices=[]
        for i in range(0,len(triangles),3):
            a,b,c=[vertices[j] for j in triangles[i:i+3]]
            u=[b[k]-a[k] for k in range(3)];v=[c[k]-a[k] for k in range(3)]
            n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            length=math.sqrt(sum(q*q for q in n));n=[q/max(length,1e-12) for q in n]
            start=len(out);out.extend([a,b,c]);ns.extend([n,n,n]);indices.extend([start,start+1,start+2])
        vertices,normals,triangles=out,ns,indices
    bounds=[[min(v[k] for v in vertices) for k in range(3)],[max(v[k] for v in vertices) for k in range(3)]]
    return {"name":name,"group":group,"block":material,"source_id":component or name,"solid":solid,
            "bounds_wir_m":bounds,"vertices":vertices,"normals":normals,"indices":triangles}


def cuboid(part,pose):
    a,b=part["bounds_wir_m"]
    vertices=[[a[0],a[1],a[2]],[b[0],a[1],a[2]],[b[0],b[1],a[2]],[a[0],b[1],a[2]],
              [a[0],a[1],b[2]],[b[0],a[1],b[2]],[b[0],b[1],b[2]],[a[0],b[1],b[2]]]
    faces=((4,5,6,7),(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7))
    indices=[j for face in faces for j in (face[0],face[1],face[2],face[0],face[2],face[3])]
    return mesh(part.get("name",part["source_id"]),part["group"],part["block"],
                [transform(p,pose) for p in vertices],indices,component=part["source_id"],solid=part["block"]!="minecraft:water")


def cone(name,group,material,x,y,z,radius,height,sides=7):
    vertices=[[x+radius*math.cos(i*2*math.pi/sides),y+radius*math.sin(i*2*math.pi/sides),z] for i in range(sides)]
    vertices.append([x,y,z+height]);indices=[]
    for i in range(sides):indices.extend([i,(i+1)%sides,sides])
    return mesh(name,group,material,vertices,indices)


def glb(meshes,palette):
    names=sorted({m["block"] for m in meshes});material_index={n:i for i,n in enumerate(names)}
    doc={"asset":{"version":"2.0","generator":"world_builder nature046 mesh"},"scene":0,
         "scenes":[{"nodes":list(range(len(meshes)))}],"nodes":[],"meshes":[],"materials":[],"accessors":[],"bufferViews":[],"buffers":[]}
    for name in names:
        color=palette[name];material={"name":name,"doubleSided":False,"pbrMetallicRoughness":{"baseColorFactor":color,"metallicFactor":0,"roughnessFactor":.95}}
        if color[3]<1:material["alphaMode"]="BLEND"
        doc["materials"].append(material)
    binary=bytearray()
    def accessor(values,component,kind,fmt,target,bounds=False):
        while len(binary)%4:binary.append(0)
        offset=len(binary)
        if kind=="SCALAR":binary.extend(struct.pack("<"+fmt*len(values),*values))
        else:binary.extend(b"".join(struct.pack("<"+fmt,*v) for v in values))
        doc["bufferViews"].append({"buffer":0,"byteOffset":offset,"byteLength":len(binary)-offset,"target":target})
        a={"bufferView":len(doc["bufferViews"])-1,"componentType":component,"count":len(values),"type":kind}
        if bounds:a.update(min=[min(v[k] for v in values) for k in range(3)],max=[max(v[k] for v in values) for k in range(3)])
        doc["accessors"].append(a);return len(doc["accessors"])-1
    for i,m in enumerate(meshes):
        # RH WIR -> RH glTF; glTFast reflects X, yielding Unity east/up/north.
        positions=[[-v[0],v[2],v[1]] for v in m["vertices"]]
        normals=[[-v[0],v[2],v[1]] for v in m["normals"]]
        p=accessor(positions,5126,"VEC3","fff",34962,True);n=accessor(normals,5126,"VEC3","fff",34962)
        ix=accessor(m["indices"],5125,"SCALAR","I",34963)
        doc["meshes"].append({"name":m["name"],"primitives":[{"attributes":{"POSITION":p,"NORMAL":n},"indices":ix,"material":material_index[m["block"]]}]})
        doc["nodes"].append({"name":m["name"],"mesh":i,"extras":{"source_id":m["name"]}})
    while len(binary)%4:binary.append(0)
    doc["buffers"].append({"byteLength":len(binary)})
    metadata=json.dumps(doc,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8");metadata+=b" "*((-len(metadata))%4)
    length=12+8+len(metadata)+8+len(binary)
    return struct.pack("<4sII",b"glTF",2,length)+struct.pack("<I4s",len(metadata),b"JSON")+metadata+struct.pack("<I4s",len(binary),b"BIN\0")+binary,material_index
