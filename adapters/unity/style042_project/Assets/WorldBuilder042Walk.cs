using System;
using System.IO;
using UnityEngine;

public sealed class WorldBuilder042Walk : MonoBehaviour
{
    [Serializable] public sealed class Route { public string group,room; public int level; public float[][] cells; }
    // Unity JsonUtility does not support nested arrays; Editor converts points.
    [Serializable] public sealed class Path { public string room; public int level; public Vector3[] points; public int[] critical_indices; }
    [Serializable] public sealed class Result
    {
        public string status="in_progress",method="Unity_PlayMode_CharacterController_continuous_routes",error;
        public int expected_routes,completed_routes,grounded_frames,frames;
        public string[] completed_rooms;
        public string unity_version;
    }
    public Path[] paths;
    public string resultPath;
    CharacterController controller;
    Result result;
    int routeIndex,pointIndex,stuck;
    float best=float.MaxValue;
    void Start()
    {
        QualitySettings.vSyncCount=0;Application.targetFrameRate=240;
        controller=GetComponent<CharacterController>();
        result=new Result { expected_routes=paths.Length,completed_rooms=new string[paths.Length],unity_version=Application.unityVersion };
        BeginRoute();
    }
    void BeginRoute()
    {
        controller.enabled=false;
        transform.position=paths[routeIndex].points[0]+Vector3.up*.025f;
        controller.enabled=true;
        pointIndex=1;stuck=0;best=float.MaxValue;
        Physics.SyncTransforms();
    }
    void Update()
    {
        if(result.status!="in_progress")return;
        result.frames++;
        if(result.frames>120000){ Finish(false,"frame_budget");return; }
        Vector3 target=paths[routeIndex].points[pointIndex];
        Vector3 delta=target-transform.position; delta.y=0;
        float distance=delta.magnitude;
        bool critical=Array.IndexOf(paths[routeIndex].critical_indices,pointIndex)>=0;
        if(distance<.06f && Mathf.Abs(transform.position.y-target.y)<(critical?.08f:.23f))
        {
            pointIndex++;stuck=0;best=float.MaxValue;
            if(pointIndex==paths[routeIndex].points.Length)
            {
                result.completed_rooms[routeIndex]=paths[routeIndex].room;
                result.completed_routes++;routeIndex++;
                if(routeIndex==paths.Length){ Finish(true,null);return; }
                BeginRoute();
            }
            return;
        }
        if(distance<best-.003f){ best=distance;stuck=0; } else stuck++;
        if(stuck>600){ Finish(false,paths[routeIndex].room+" blocked at point "+pointIndex+" position "+transform.position+" target "+target);return; }
        Vector3 movement=delta.normalized*Mathf.Min(.04f,distance);
        movement.y=-.045f;
        controller.Move(movement);
        if(controller.isGrounded)result.grounded_frames++;
    }
    void Finish(bool pass,string error)
    {
        result.status=pass?"pass":"fail";result.error=error;
        Directory.CreateDirectory(System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(resultPath)));
        File.WriteAllText(resultPath,JsonUtility.ToJson(result,true));
#if UNITY_EDITOR
        if(Application.isBatchMode)UnityEditor.EditorApplication.Exit(pass?0:1);
        else UnityEditor.EditorApplication.isPlaying=false;
#endif
    }
}
