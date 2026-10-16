using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

public static class WorldBuilderCityBuilder
{
    static string Case=>Environment.GetEnvironmentVariable("WB_CITY_CASE")=="Nature046"?"Nature046":"City";
    static string Base=>"Assets/Generated/"+Case+"/";
    static string ScenePath=>Base+"Arcane"+Case+".unity";
    static string Evidence=>Environment.GetEnvironmentVariable("WB_CITY045_EVIDENCE")??Path.GetFullPath("Evidence/City");
    [Serializable] sealed class Piece { public string name,source_id,group,component;public int material;public bool solid; }
    [Serializable] sealed class Manifest { public string source_id,source_revision_id,glb_sha256;public int piece_count;public Piece[] pieces; }
    [Serializable] sealed class PieceBounds { public string name;public Vector3 min,max; }
    [Serializable] sealed class BoundsSet { public PieceBounds[] pieces; }
    [Serializable] sealed class Pbr { public float[] baseColorFactor; }
    [Serializable] sealed class GMat { public Pbr pbrMetallicRoughness; }
    [Serializable] sealed class GDoc { public GMat[] materials; }
    [Serializable] sealed class ViewConfig
    {
        public float street_y,river_x,castle_x,region_m;
        public Vector3 overviewPosition,overviewTarget,streetPosition,streetTarget,riverPosition,riverTarget,castlePosition,castleTarget,spawnPosition;
    }
    [Serializable] sealed class PathSet { public WorldBuilder042Walk.Path[] paths; }
    [Serializable] sealed class Report
    {
        public string status="in_progress",error,source_revision_id,glb_sha256,unity_version;
        public int expected_pieces,mapped_pieces,bounds_checked,mesh_colliders,render_batches,batched_source_meshes;
    }
    static void Check(bool condition,string message){if(!condition)throw new Exception(message);}
    static Manifest ReadManifest()
    {
        var manifest=JsonUtility.FromJson<Manifest>(File.ReadAllText(Base+"manifest.json"));
        using(var sha=SHA256.Create())
            Check("sha256:"+BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(Base+"scene.glb"))).Replace("-","").ToLowerInvariant()==manifest.glb_sha256,"GLB hash differs");
        return manifest;
    }
    static Bounds WorldBounds(MeshFilter filter)
    {
        var b=filter.sharedMesh.bounds;var result=new Bounds(filter.transform.TransformPoint(b.min),Vector3.zero);
        for(int x=0;x<2;x++)for(int y=0;y<2;y++)for(int z=0;z<2;z++)
            result.Encapsulate(filter.transform.TransformPoint(new Vector3(x==0?b.min.x:b.max.x,y==0?b.min.y:b.max.y,z==0?b.min.z:b.max.z)));
        return result;
    }
    static Dictionary<string,MeshFilter> Filters(GameObject root)=>root.GetComponentsInChildren<MeshFilter>().ToDictionary(f=>f.name);
    static void CheckBounds(MeshFilter filter,PieceBounds expected)
    {
        Bounds actual=WorldBounds(filter);
        Check(Vector3.Distance(actual.min,expected.min)<.005f&&Vector3.Distance(actual.max,expected.max)<.005f,"Bounds differ: "+expected.name);
    }
    [MenuItem("World Builder/045/Build Delivered City")]
    public static void Build()
    {
        Directory.CreateDirectory(Evidence);
        var report=new Report {unity_version=Application.unityVersion};
        try
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            Manifest manifest=ReadManifest();report.source_revision_id=manifest.source_revision_id;report.glb_sha256=manifest.glb_sha256;report.expected_pieces=manifest.piece_count;
            var prefab=AssetDatabase.LoadAssetAtPath<GameObject>(Base+"scene.glb");Check(prefab!=null,"glTFast did not import the city");
            var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var root=UnityEngine.Object.Instantiate(prefab);root.name=manifest.source_id;
            var filters=Filters(root);
            var bounds=JsonUtility.FromJson<BoundsSet>(File.ReadAllText(Base+"unity_bounds.json")).pieces.ToDictionary(p=>p.name);
            byte[] glb=File.ReadAllBytes(Base+"scene.glb");int size=BitConverter.ToInt32(glb,12);
            var document=JsonUtility.FromJson<GDoc>(Encoding.UTF8.GetString(glb,20,size).TrimEnd(' ','\0'));
            var materials=new Material[document.materials.Length];
            for(int i=0;i<materials.Length;i++)
            {
                string path=Base+"city_material_"+i+".mat";var material=AssetDatabase.LoadAssetAtPath<Material>(path);
                if(material==null){material=new Material(Shader.Find("Standard"));AssetDatabase.CreateAsset(material,path);}
                var c=document.materials[i].pbrMetallicRoughness.baseColorFactor;material.color=new Color(c[0],c[1],c[2],c[3]);
                material.SetFloat("_Glossiness",.12f);material.enableInstancing=true;
                if(c[3]<.99f){material.SetFloat("_Mode",3);material.SetInt("_SrcBlend",(int)BlendMode.SrcAlpha);material.SetInt("_DstBlend",(int)BlendMode.OneMinusSrcAlpha);material.SetInt("_ZWrite",0);material.EnableKeyword("_ALPHAPREMULTIPLY_ON");material.renderQueue=3000;}
                materials[i]=material;
            }
            var grouped=new Dictionary<string,List<Piece>>();
            var bridgeMaterials=new Dictionary<int,Material>();
            foreach(var piece in manifest.pieces)
            {
                Check(filters.ContainsKey(piece.name),"Missing mesh "+piece.name);var filter=filters[piece.name];CheckBounds(filter,bounds[piece.name]);report.bounds_checked++;
                var pieceMaterial=materials[piece.material];
                if(Case=="Nature046"&&piece.group=="bridges")
                {
                    if(!bridgeMaterials.ContainsKey(piece.material))
                    {
                        string bridgePath=Base+"bridge_material_"+piece.material+".mat";
                        var bridge=AssetDatabase.LoadAssetAtPath<Material>(bridgePath);
                        var shader=Shader.Find("WorldBuilder/BridgeDepthBias");Check(shader!=null&&shader.isSupported,"Bridge depth-bias shader unavailable");
                        if(bridge==null){bridge=new Material(shader);AssetDatabase.CreateAsset(bridge,bridgePath);}
                        bridge.shader=shader;bridge.color=pieceMaterial.color;bridge.SetFloat("_Glossiness",.12f);EditorUtility.SetDirty(bridge);
                        bridgeMaterials[piece.material]=bridge;
                    }
                    pieceMaterial=bridgeMaterials[piece.material];
                }
                filter.GetComponent<MeshRenderer>().sharedMaterial=pieceMaterial;
                if(piece.solid){filter.gameObject.AddComponent<MeshCollider>().sharedMesh=filter.sharedMesh;report.mesh_colliders++;}
                Vector3 centre=WorldBounds(filter).center;
                string key=$"{Mathf.FloorToInt(centre.x/64)}_{Mathf.FloorToInt(centre.z/64)}_{piece.material}";
                if(Case=="Nature046"&&piece.group=="bridges")key+="_bridge";
                if(!grouped.ContainsKey(key))grouped[key]=new List<Piece>();grouped[key].Add(piece);
                report.mapped_pieces++;
            }
            Directory.CreateDirectory(Base+"BatchMeshes");AssetDatabase.Refresh();
            var batches=new GameObject("City Render Batches");
            foreach(var pair in grouped.OrderBy(p=>p.Key))
            {
                string path=Base+"BatchMeshes/"+pair.Key+".asset";
                var mesh=AssetDatabase.LoadAssetAtPath<Mesh>(path);bool fresh=mesh==null;
                if(fresh)mesh=new Mesh();else mesh.Clear();mesh.name="city_batch_"+pair.Key;mesh.indexFormat=IndexFormat.UInt32;
                mesh.CombineMeshes(pair.Value.Select(p=>new CombineInstance {mesh=filters[p.name].sharedMesh,transform=filters[p.name].transform.localToWorldMatrix}).ToArray(),true,true);
                if(fresh)AssetDatabase.CreateAsset(mesh,path);else EditorUtility.SetDirty(mesh);
                var go=new GameObject(mesh.name);go.transform.SetParent(batches.transform,false);go.AddComponent<MeshFilter>().sharedMesh=mesh;
                go.AddComponent<MeshRenderer>().sharedMaterial=filters[pair.Value[0].name].GetComponent<MeshRenderer>().sharedMaterial;
                go.AddComponent<WorldBuilderCityBatch>().sourceNames=pair.Value.Select(p=>p.name).ToArray();
                foreach(var piece in pair.Value)filters[piece.name].GetComponent<MeshRenderer>().enabled=false;
                report.render_batches++;report.batched_source_meshes+=pair.Value.Count;
            }
            Check(report.batched_source_meshes==manifest.piece_count,"Render batch omitted source geometry");
            RenderSettings.ambientMode=AmbientMode.Flat;RenderSettings.ambientLight=new Color(.70f,.72f,.74f);
            var sun=new GameObject("Sun").AddComponent<Light>();sun.type=LightType.Directional;sun.intensity=1.2f;sun.shadows=LightShadows.Soft;sun.transform.rotation=Quaternion.Euler(48,-35,0);
            QualitySettings.shadowDistance=220;QualitySettings.vSyncCount=0;
            var view=JsonUtility.FromJson<ViewConfig>(File.ReadAllText(Base+"city_view.json"));
            var camera=new GameObject("City Camera").AddComponent<Camera>();camera.tag="MainCamera";camera.farClipPlane=view.region_m>0?2400:1600;camera.nearClipPlane=view.region_m>0?.3f:.1f;camera.fieldOfView=48;
            camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(.75f,.84f,.93f);
            var explorer=camera.gameObject.AddComponent<WorldBuilderCityExplorer>();explorer.streetY=view.street_y;explorer.riverX=view.river_x;explorer.castleX=view.castle_x;
            if(view.region_m>0)
            {
                explorer.regionM=view.region_m;explorer.overviewPosition=view.overviewPosition;explorer.overviewTarget=view.overviewTarget;
                explorer.streetPosition=view.streetPosition;explorer.streetTarget=view.streetTarget;explorer.riverPosition=view.riverPosition;explorer.riverTarget=view.riverTarget;
                explorer.castlePosition=view.castlePosition;explorer.castleTarget=view.castleTarget;explorer.spawnPosition=view.spawnPosition;
            }
            SetOverview(camera,view);
            Physics.SyncTransforms();EditorSceneManager.SaveScene(scene,ScenePath);AssetDatabase.SaveAssets();
            RenderViews(camera,view);report.status="pass";
        }
        catch(Exception error){report.status="fail";report.error=error.ToString();Debug.LogException(error);}
        File.WriteAllText(Path.Combine(Evidence,"target_validation.json"),JsonUtility.ToJson(report,true));
        Check(report.status=="pass",report.error);
    }
    static void Render(Camera camera,string name,Vector3 position,Vector3 target,float fov)
    {
        camera.transform.position=position;camera.transform.LookAt(target);camera.fieldOfView=fov;
        var texture=new RenderTexture(1600,1000,24);camera.targetTexture=texture;camera.Render();
        var old=RenderTexture.active;RenderTexture.active=texture;
        var image=new Texture2D(1600,1000,TextureFormat.RGB24,false);image.ReadPixels(new Rect(0,0,1600,1000),0,0);image.Apply();
        File.WriteAllBytes(Path.Combine(Evidence,name+".png"),image.EncodeToPNG());
        RenderTexture.active=old;camera.targetTexture=null;texture.Release();UnityEngine.Object.DestroyImmediate(image);
    }
    static void RenderViews(Camera camera,ViewConfig view)
    {
        if(view.region_m>0)
        {
            Render(camera,"overview",view.overviewPosition,view.overviewTarget,48);
            Render(camera,"street",view.streetPosition,view.streetTarget,60);
            Render(camera,"river",view.riverPosition,view.riverTarget,60);
            Render(camera,"castle",view.castlePosition,view.castleTarget,55);
            return;
        }
        Render(camera,"overview",new Vector3(720,520,-240),new Vector3(256,1,240),48);
        Render(camera,"street",new Vector3(72,5,view.street_y),new Vector3(184,4,view.street_y+6),65);
        Render(camera,"river",new Vector3(view.river_x+45,28,view.street_y-55),new Vector3(view.river_x,1,view.street_y+40),60);
        Render(camera,"castle",new Vector3(view.castle_x+95,65,387),new Vector3(view.castle_x,8,462),55);
    }
    public static void Reopen()
    {
        Directory.CreateDirectory(Evidence);EditorSceneManager.OpenScene(ScenePath);
        var manifest=ReadManifest();var root=GameObject.Find(manifest.source_id);Check(root!=null,"Saved source root missing");
        var filters=Filters(root);var bounds=JsonUtility.FromJson<BoundsSet>(File.ReadAllText(Base+"unity_bounds.json")).pieces.ToDictionary(p=>p.name);
        var report=new Report {unity_version=Application.unityVersion,source_revision_id=manifest.source_revision_id,glb_sha256=manifest.glb_sha256,expected_pieces=manifest.piece_count};
        foreach(var piece in manifest.pieces)
        {
            Check(filters.ContainsKey(piece.name),"Saved source missing: "+piece.name);var filter=filters[piece.name];CheckBounds(filter,bounds[piece.name]);
            if(piece.solid){Check(filter.GetComponent<MeshCollider>()!=null,"Saved collider missing");report.mesh_colliders++;}
            report.mapped_pieces++;report.bounds_checked++;
        }
        var seen=new HashSet<string>();
        foreach(var batch in UnityEngine.Object.FindObjectsByType<WorldBuilderCityBatch>(FindObjectsSortMode.None))
        {
            Check(batch.GetComponent<MeshFilter>().sharedMesh!=null&&batch.GetComponent<MeshRenderer>().enabled,"Saved render batch missing");
            foreach(string name in batch.sourceNames)Check(filters.ContainsKey(name)&&seen.Add(name),"Bad/duplicate batch membership");
            report.render_batches++;report.batched_source_meshes+=batch.sourceNames.Length;
        }
        Check(seen.Count==manifest.piece_count,"Saved batches omit source meshes");report.status="pass";
        File.WriteAllText(Path.Combine(Evidence,"target_reopen.json"),JsonUtility.ToJson(report,true));
    }
    public static void VerifyWalk()
    {
        Reopen();var paths=JsonUtility.FromJson<PathSet>(File.ReadAllText(Base+"unity_paths.json"));
        var body=new GameObject("City Automated Walking Validator");var controller=body.AddComponent<CharacterController>();
        controller.height=1.8f;controller.radius=.28f;controller.center=new Vector3(0,.9f,0);controller.skinWidth=.015f;controller.stepOffset=.3f;controller.slopeLimit=50;
        foreach(var explorer in UnityEngine.Object.FindObjectsByType<WorldBuilderCityExplorer>(FindObjectsSortMode.None))explorer.enabled=false;
        var walker=body.AddComponent<WorldBuilderCityWalk>();walker.paths=paths.paths;walker.resultPath=Path.Combine(Evidence,"walk_validation.json");
        walker.terrainGravity=Case=="Nature046";
        EditorSceneManager.SaveScene(body.scene,Base+"Arcane"+Case+"WalkValidation.unity");EditorApplication.isPlaying=true;
    }
    [MenuItem("World Builder/045/Open Delivered City")]
    public static void Open()=>EditorSceneManager.OpenScene(ScenePath,OpenSceneMode.Single);
    [MenuItem("World Builder/046/Open Organic Landscape")]
    public static void OpenNature()=>EditorSceneManager.OpenScene("Assets/Generated/Nature046/ArcaneNature046.unity",OpenSceneMode.Single);
    static void SetOverview(Camera camera,ViewConfig view)
    {
        camera.transform.position=view.region_m>0?view.overviewPosition:new Vector3(720,520,-240);
        camera.transform.LookAt(view.region_m>0?view.overviewTarget:new Vector3(256,1,240));camera.fieldOfView=48;
    }
    public static void RenderSaved()
    {
        Reopen();var camera=Camera.main;
        var view=JsonUtility.FromJson<ViewConfig>(File.ReadAllText(Base+"city_view.json"));SetOverview(camera,view);
        EditorSceneManager.SaveScene(camera.gameObject.scene,ScenePath);
        RenderViews(camera,view);
    }
}
