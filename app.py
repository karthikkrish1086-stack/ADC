<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2023.1">
  <Nodes>
    <!-- Stream A: Stores -> Create Points -> Buffer (trade areas) -->
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput"><Position x="60" y="80" /></GuiSettings>
      <Properties>
        <Configuration><File>stores.csv</File></Configuration>
        <Annotation DisplayMode="0"><Name>Input Stores</Name></Annotation>
      </Properties>
      <EngineSettings EngineDllEntryPoint="AlteryxDbFileInput" />
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxSpatialPluginsGui.CreatePoints.CreatePoints"><Position x="200" y="80" /></GuiSettings>
      <Properties>
        <Configuration>
          <XField field="Longitude" /><YField field="Latitude" /><OutputField field="StoreLoc" />
        </Configuration>
        <Annotation DisplayMode="0"><Name>Store Points</Name></Annotation>
      </Properties>
      <EngineSettings EngineDllEntryPoint="AlteryxCreatePoints" />
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxSpatialPluginsGui.Buffer.Buffer"><Position x="340" y="80" /></GuiSettings>
      <Properties>
        <Configuration>
          <SpatialField field="StoreLoc" />
          <BufferSize>10</BufferSize>
          <BufferUnits>Miles</BufferUnits>
          <OutputField field="TradeArea" />
        </Configuration>
        <Annotation DisplayMode="0"><Name>10mi Trade Area</Name></Annotation>
      </Properties>
      <EngineSettings EngineDllEntryPoint="AlteryxBuffer" />
    </Node>
    <!-- Stream B: Customers -> Create Points -->
    <Node ToolID="4">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput"><Position x="60" y="240" /></GuiSettings>
      <Properties>
        <Configuration><File>customers.csv</File></Configuration>
        <Annotation DisplayMode="0"><Name>Input Customers</Name></Annotation>
      </Properties>
      <EngineSettings EngineDllEntryPoint="AlteryxDbFileInput" />
    </Node>
    <Node ToolID="5">
      <GuiSettings Plugin="AlteryxSpatialPluginsGui.CreatePoints.CreatePoints"><Position x="200" y="240" /></GuiSettings>
      <Properties>
        <Configuration>
          <XField field="Longitude" /><YField field="Latitude" /><OutputField field="CustLoc" />
        </Configuration>
        <Annotation DisplayMode="0"><Name>Customer Points</Name></Annotation>
      </Properties>
      <EngineSettings EngineDllEntryPoint="AlteryxCreatePoints" />
    </Node>
    <!-- Spatial Match: which customers fall inside which trade area (point in polygon) -->
    <Node ToolID="6">
      <GuiSettings Plugin="AlteryxSpatialPluginsGui.SpatialMatch.SpatialMatch"><Position x="480" y="160" /></GuiSettings>
      <Properties>
        <Configuration>
          <TargetField field="CustLoc" />
          <UniverseField field="TradeArea" />
          <MatchType>Where target Intersects universe</MatchType>
        </Configuration>
        <Annotation DisplayMode="0"><Name>Customers in Trade Areas</Name></Annotation>
      </Properties>
      <EngineSettings EngineDllEntryPoint="AlteryxSpatialMatch" />
    </Node>
    <!-- Multi-field formula: distance + spend score -->
    <Node ToolID="7">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"><Position x="620" y="160" /></GuiSettings>
      <Properties>
        <Configuration>
          <FormulaFields>
            <FormulaField expression="DistanceInMiles([CustLoc], [StoreLoc])" field="DistToStore" size="8" type="Double" />
            <FormulaField expression="IF [LifetimeValue] &gt; 5000 AND [DistToStore] &lt; 5 THEN &quot;Priority&quot; ELSEIF [LifetimeValue] &gt; 2000 THEN &quot;Standard&quot; ELSE &quot;Low&quot; ENDIF" field="CustomerSegment" size="12" type="String" />
          </FormulaFields>
        </Configuration>
        <Annotation DisplayMode="0"><Name>Distance + Segment</Name></Annotation>
      </Properties>
      <EngineSettings EngineDllEntryPoint="AlteryxFormula" />
    </Node>
    <!-- Filter to matched priority/standard customers -->
    <Node ToolID="8">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter.Filter"><Position x="760" y="160" /></GuiSettings>
      <Properties>
        <Configuration>
          <Expression>[CustomerSegment] != "Low"</Expression>
          <Mode>Custom</Mode>
        </Configuration>
        <Annotation DisplayMode="0"><Name>Drop Low Segment</Name></Annotation>
      </Properties>
      <EngineSettings EngineDllEntryPoint="AlteryxFilter" />
    </Node>
    <!-- Summarize: store-level capture metrics -->
    <Node ToolID="9">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Summarize.Summarize"><Position x="900" y="160" /></GuiSettings>
      <Properties>
        <Configuration>
          <SummarizeFields>
            <SummarizeField field="StoreID" action="GroupBy" rename="StoreID" />
            <SummarizeField field="StoreName" action="GroupBy" rename="StoreName" />
            <SummarizeField field="CustomerID" action="CountDistinct" rename="CapturedCustomers" />
            <SummarizeField field="LifetimeValue" action="Sum" rename="CapturedLTV" />
            <SummarizeField field="DistToStore" action="Avg" rename="AvgCustDistance" />
          </SummarizeFields>
        </Configuration>
        <Annotation DisplayMode="0"><Name>Store Capture Metrics</Name></Annotation>
      </Properties>
      <EngineSettings EngineDllEntryPoint="AlteryxSummarize" />
    </Node>
    <Node ToolID="10">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput"><Position x="1040" y="160" /></GuiSettings>
      <Properties>
        <Configuration><File>store_trade_area_capture.csv</File></Configuration>
        <Annotation DisplayMode="0"><Name>Output</Name></Annotation>
      </Properties>
      <EngineSettings EngineDllEntryPoint="AlteryxDbFileOutput" />
    </Node>
  </Nodes>
  <Connections>
    <Connection><Origin ToolID="1" Connection="Output" /><Destination ToolID="2" Connection="Input" /></Connection>
    <Connection><Origin ToolID="2" Connection="Output" /><Destination ToolID="3" Connection="Input" /></Connection>
    <Connection><Origin ToolID="4" Connection="Output" /><Destination ToolID="5" Connection="Input" /></Connection>
    <Connection><Origin ToolID="5" Connection="Output" /><Destination ToolID="6" Connection="Targets" /></Connection>
    <Connection><Origin ToolID="3" Connection="Output" /><Destination ToolID="6" Connection="Universe" /></Connection>
    <Connection><Origin ToolID="6" Connection="Matched" /><Destination ToolID="7" Connection="Input" /></Connection>
    <Connection><Origin ToolID="7" Connection="Output" /><Destination ToolID="8" Connection="Input" /></Connection>
    <Connection><Origin ToolID="8" Connection="True" /><Destination ToolID="9" Connection="Input" /></Connection>
    <Connection><Origin ToolID="9" Connection="Output" /><Destination ToolID="10" Connection="Input" /></Connection>
  </Connections>
</AlteryxDocument>
